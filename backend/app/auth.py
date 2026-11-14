import bcrypt
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session, select

from .config import get_settings
from .db import get_session
from .models import User

COOKIE = "acv_session"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="acv-session")


def make_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id})


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "não autenticado")
    try:
        data = _serializer().loads(token, max_age=get_settings().session_days * 86400)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "sessão inválida")
    user = session.get(User, data.get("uid"))
    if not user:
        raise HTTPException(401, "usuário não existe")
    return user


def upsert_user(session: Session, username: str, password: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if user:
        user.password_hash = hash_password(password)
    else:
        user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def bootstrap_users(session: Session) -> None:
    """Cria os usuários de BOOTSTRAP_USERS só se ainda não existirem (não sobrescreve senha)."""
    raw = get_settings().bootstrap_users.strip()
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if ":" not in pair:
            continue
        username, password = pair.split(":", 1)
        exists = session.exec(select(User).where(User.username == username.strip())).first()
        if not exists and password:
            upsert_user(session, username.strip(), password)
