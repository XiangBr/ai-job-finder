"""Uso:
  python -m app.cli create-user <usuario> [senha]          # cria/troca senha (sem senha: gera uma aleatória)
  python -m app.cli import-cv <usuario> <arquivo> [--como-esta] [--filtros filtros.yaml]
                                                           # sobe o CV, gera fatos + CV base com a IA e salva no perfil
  python -m app.cli set-filters <usuario> <filtros.yaml>   # troca os filtros de busca do usuário
  python -m app.cli run [usuario]                          # roda uma busca agora (sem usuário: todos os perfis)
  python -m app.cli analyze [usuario]                      # analisa vagas pendentes
  python -m app.cli check-ai                               # testa o provedor de IA configurado
"""

import secrets
import sys
from pathlib import Path

from sqlmodel import Session, select

from .db import engine, init_db


def _user(s: Session, username: str):
    from .models import User

    u = s.exec(select(User).where(User.username == username)).first()
    if not u:
        sys.exit(f"usuário '{username}' não existe (crie com: python -m app.cli create-user {username})")
    return u


def _profiles(s: Session, username: str | None):
    from .profile import all_profiles, get_profile, migrate_profiles, seed_profile

    migrate_profiles(s)
    seed_profile(s)
    return [get_profile(s, _user(s, username))] if username else all_profiles(s)


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__)
        return
    init_db()
    cmd, args = argv[0], argv[1:]
    if cmd == "create-user" and args:
        from .auth import upsert_user

        pw = args[1] if len(args) > 1 else secrets.token_urlsafe(9)
        with Session(engine) as s:
            upsert_user(s, args[0], pw)
        print(f"usuário: {args[0]}\nsenha:   {pw}")

    elif cmd == "import-cv" and len(args) >= 2:
        from . import cv_import
        from .models import now
        from .profile import get_profile

        username, arquivo = args[0], Path(args[1])
        modo = "como_esta" if "--como-esta" in args else "otimizar"
        filtros_file = args[args.index("--filtros") + 1] if "--filtros" in args else None
        data = arquivo.read_bytes()
        texto = cv_import.extract_text(arquivo.name, data)
        with Session(engine) as s:
            p = get_profile(s, _user(s, username))
            cv_import.save_original(p.id, arquivo.name, data)
            if filtros_file:
                p.filtros_yaml = Path(filtros_file).read_text(encoding="utf-8")
            print(f"{len(texto)} caracteres extraídos; IA trabalhando (modo {modo})...")
            out, modelo = cv_import.run_import(texto, p.filtros_yaml, modo)
            p.nome = out.nome or p.nome
            p.fatos_yaml, p.cv_base_md, p.atualizado_em = out.fatos_yaml, out.cv_base_md, now()
            s.add(p)
            s.commit()
        print(f"perfil de {username} salvo ({modelo})\n\nCorreções sugeridas:")
        print("\n".join(f"- {c}" for c in out.correcoes))
        print("\nPerguntas para completar o CV:")
        print("\n".join(f"- {q}" for q in out.perguntas))

    elif cmd == "set-filters" and len(args) == 2:
        import yaml

        from .models import now
        from .profile import get_profile

        text = Path(args[1]).read_text(encoding="utf-8")
        yaml.safe_load(text)
        with Session(engine) as s:
            p = get_profile(s, _user(s, args[0]))
            p.filtros_yaml, p.atualizado_em = text, now()
            s.add(p)
            s.commit()
        print(f"filtros de {args[0]} salvos")

    elif cmd == "run":
        from .models import Run
        from .pipeline import run_search

        with Session(engine) as s:
            ids = [p.id for p in _profiles(s, args[0] if args else None)]
        for pid in ids:
            rid = run_search(pid, "manual", force=True)
            with Session(engine) as s:
                r = s.get(Run, rid) if rid else None
                print(f"--- perfil {pid}\n" + (r.log if r else "outra busca já está rodando"))

    elif cmd == "analyze":
        from .pipeline import analyze_pending

        with Session(engine) as s:
            for p in _profiles(s, args[0] if args else None):
                lines: list[str] = []
                analyze_pending(s, p, lines)
                print(f"--- perfil {p.id}\n" + "\n".join(lines))

    elif cmd == "check-ai":
        from pydantic import BaseModel

        from .ai.providers import get_provider
        from .config import get_settings

        class Pong(BaseModel):
            resposta: str
            soma: int

        st = get_settings()
        prov = get_provider()
        print(f"provedor: {prov.name} | triagem: {st.ai_model_triage or '(padrão)'} | CV: {st.ai_model_cv or '(padrão)'}")
        out = prov.structured("Responda em JSON.", "Diga 'ok' em `resposta` e quanto é 2+3 em `soma`.",
                              Pong, st.ai_model_triage, "low")
        print(f"resposta: {out.resposta} | 2+3 = {out.soma}")

    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
