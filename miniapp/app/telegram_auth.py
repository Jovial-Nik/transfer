import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int) -> dict:
    """Проверяет подпись initData из Telegram WebApp и возвращает данные пользователя."""
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise AuthError("hash отсутствует")

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("неверная подпись")

    auth_date = int(fields.get("auth_date", 0))
    if max_age and time.time() - auth_date > max_age:
        raise AuthError("initData устарела")

    user = json.loads(fields.get("user", "{}"))
    if "id" not in user:
        raise AuthError("нет пользователя")
    return user
