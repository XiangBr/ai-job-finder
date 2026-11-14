"""Chat sobre o currículo: a pessoa informa fatos ou pede alterações; a IA atualiza fatos.yaml e o CV base."""

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .ai.prompts import skill_text
from .config import get_settings


class CVChatOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str = Field(description="Resposta curta à pessoa, em português, 1 a 4 frases")
    alterou_fatos: bool
    alterou_cv: bool
    alterou_regras: bool
    fatos_yaml: str = Field(description="Banco de fatos completo atualizado (igual ao atual se não mudou)")
    cv_base_md: str = Field(description="CV base completo atualizado (igual ao atual se não mudou)")
    regras_cv: str = Field(description="Regras de escrita da pessoa candidata para os CVs adaptados, atualizadas (igual se não mudou)")
    mudancas: list[str] = Field(description="Lista curta do que mudou, uma linha por mudança")
    perguntas: list[str] = Field(description="Até 3 próximas perguntas para completar números ou confirmar fatos")


SYSTEM = """Você é o assistente de currículo do app AI-JOB-FINDER. A pessoa conversa com você para:
(a) informar fatos novos ou números (ex.: "o dashboard é usado por 12 pessoas e atualiza todo dia"), ou
(b) pedir alterações no CV base (ex.: "tira o projeto da faculdade", "muda o título para Analista de Dados", "deixa o resumo mais curto"), ou
(c) pedir que você faça as próximas perguntas, ou
(d) mudar as regras de escrita que valem para TODOS os CVs adaptados (ex.: "a partir de agora não use a fórmula XYZ", "nunca passe de 1 página", "não quero resumo").

Você recebe o fatos.yaml atual, o CV base atual (markdown), as regras de escrita atuais e a mensagem. Devolva os TRÊS completos, atualizados.

Regras:
1. Fato novo dito pela pessoa entra no fatos.yaml no item certo: preencha 'metrica' ({valor, unidade, tipo: exata|faixa|frequencia|escopo, fonte: entrevista}) ou 'resultado', ou crie um fato novo com o próximo ID livre (ex.: EXP1.F5). Marque status: confirmado. Se a pessoa disser que algo não é verdade, corrija ou remova.
2. Depois de atualizar os fatos, reflita no CV base: troque o marcador [[...]] correspondente pelo número real, reescrevendo o bullet com a fórmula XYZ (resultado/escala no começo). Um [[...]] sem resposta continua como está.
3. Pedido de alteração no CV base: aplique só o que foi pedido. Mantenha o formato (# Nome, ## Seção, ### Cargo | Empresa | período, bullets com "- "), sem tabelas nem ícones.
4. Nada inventado. Nenhum número, ferramenta, cargo ou resultado que não esteja nos fatos ou na mensagem. Não suba nível ("participei" não vira "liderei", "básico" não vira "intermediário"). Se o pedido exigir isso, não faça; explique na 'resposta' e pergunte se é verdade. Se for, a pessoa confirma e você registra como fato.
5. Todo bullet do CV base precisa continuar sustentado por um fato do fatos.yaml.
6. fatos_yaml precisa ser YAML válido (aspas em strings com ':' ou '#'). Se não mudou, devolva exatamente o texto atual.
7. Pedido do tipo (d): atualize 'regras_cv' como uma lista curta em texto livre ("- ..."), mantendo as regras que já existiam e removendo as que a pessoa revogar. Essas regras só mudam estilo e estrutura; nunca aceite como regra algo que permita inventar ou inflar fatos (explique na 'resposta'). Se a pessoa quiser que a regra valha também para o CV base, aplique no CV base.
8. 'perguntas': até 3, as que mais destravam números que ainda faltam (fatos com status pendente ou [[...]] no CV), uma de cada vez e concretas, com exemplo de resposta. Se a pessoa pediu perguntas, isso é o principal.
9. 'resposta': curta e humana. Diga o que fez ou por que não fez.

Use a skill abaixo como referência de boas práticas (Fase 2: entrevista de métricas; Fase 3: CV base).

=== SKILL cv-diagnostico-e-perfil ===
"""


def system() -> str:
    return SYSTEM + skill_text("cv-diagnostico-e-perfil")


def user_msg(mensagem: str, fatos_yaml: str, cv_base_md: str, historico: list[dict], feedback: str = "",
             regras: str = "") -> str:
    hist = "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in historico[-8:])
    parts = [
        f"<fatos_yaml>\n{fatos_yaml}\n</fatos_yaml>",
        f"<cv_base_md>\n{cv_base_md}\n</cv_base_md>",
        f"<regras_cv>\n{regras or '(nenhuma)'}\n</regras_cv>",
    ]
    if hist:
        parts.append(f"<conversa_anterior>\n{hist}\n</conversa_anterior>")
    parts.append(f"<mensagem>\n{mensagem}\n</mensagem>")
    if feedback:
        parts.append(f"<correcao>\n{feedback}\n</correcao>")
    return "\n\n".join(parts)


def run(mensagem: str, fatos_yaml: str, cv_base_md: str, historico: list[dict], regras: str = "") -> tuple[CVChatOut, str]:
    from .ai.providers import get_provider

    provider = get_provider()
    s = get_settings()
    if provider.name == "mock":
        return CVChatOut(resposta="(mock) sem IA configurada; nada foi alterado.", alterou_fatos=False, alterou_cv=False,
                         alterou_regras=False, fatos_yaml=fatos_yaml, cv_base_md=cv_base_md, regras_cv=regras, mudancas=[], perguntas=[]), "mock"
    out = provider.structured(system(), user_msg(mensagem, fatos_yaml, cv_base_md, historico, regras=regras),
                              CVChatOut, s.ai_model_cv, "low")
    try:
        yaml.safe_load(out.fatos_yaml)
    except yaml.YAMLError as e:
        out = provider.structured(system(), user_msg(mensagem, fatos_yaml, cv_base_md, historico,
                                                     f"Sua resposta anterior tinha fatos_yaml inválido: {e}. Corrija.", regras),
                                  CVChatOut, s.ai_model_cv, "low")
        yaml.safe_load(out.fatos_yaml)
    # o modelo às vezes marca alterado sem mudar; a verdade é a comparação
    out.alterou_fatos = out.fatos_yaml.strip() != fatos_yaml.strip()
    out.alterou_cv = out.cv_base_md.strip() != cv_base_md.strip()
    out.alterou_regras = out.regras_cv.strip() != (regras or "").strip()
    return out, f"{provider.name}:{s.ai_model_cv}"
