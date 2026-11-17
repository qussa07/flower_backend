import os
from typing import Any

import httpx
from fastapi import HTTPException


class Auth4AppExpired(Exception):
    """Заявка истекла или не принадлежит проекту."""


class Auth4AppClient:
    URLS = (
        "https://api.auth4app.com/rpc/auth",
        "https://api2.auth4app.com/rpc/auth",
        "https://api3.auth4app.com/rpc/auth",
    )

    def _request(self, method: str, params: dict) -> Any:
        # authStatus не требует ключа.
        if method != "authStatus":
            api_key = os.getenv("AUTH4APP_API_KEY")
            if not api_key:
                raise HTTPException(
                    status_code=503,
                    detail="Вход по телефону не настроен",
                )
            params = {**params, "api_key": api_key}

        with httpx.Client(timeout=10.0) as client:
            for url in self.URLS:
                try:
                    response = client.post(
                        url,
                        json={"method": method, "params": params},
                    )
                except httpx.RequestError:
                    continue

                if response.status_code >= 500:
                    continue

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail="Ошибка сервиса подтверждения телефона",
                    )

                try:
                    payload = response.json()
                except ValueError:
                    raise HTTPException(
                        status_code=502,
                        detail="Некорректный ответ Auth4App",
                    ) from None

                if not isinstance(payload, dict):
                    raise HTTPException(
                        status_code=502,
                        detail="Некорректный ответ Auth4App",
                    )

                # Auth4App может вернуть ошибку с HTTP 200.
                if payload.get("success") is not True:
                    error = payload.get("error")
                    if (
                        method == "codeResult"
                        and isinstance(error, dict)
                        and error.get("type") == "VALIDATION_ERROR"
                        and error.get("message") == "Not found"
                    ):
                        raise Auth4AppExpired()

                    raise HTTPException(
                        status_code=502,
                        detail="Auth4App не смог выполнить запрос",
                    )

                if "result" not in payload:
                    raise HTTPException(
                        status_code=502,
                        detail="Некорректный ответ Auth4App",
                    )

                return payload["result"]

        raise HTTPException(
            status_code=503,
            detail="Auth4App временно недоступен",
        )

    def create_code(self, phone: str) -> dict:
        return self._request(
            "codeGet",
            {"phone": phone, "lang": "ru"},
        )

    def get_status(self, code_id: str) -> str:
        return self._request(
            "authStatus",
            {"code_id": code_id},
        )

    def get_result(self, code_id: str) -> dict:
        return self._request(
            "codeResult",
            {"code_id": code_id},
        )