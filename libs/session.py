"""
Copyright 2022 laynholt

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""
Источники:
    1) https://github.com/AlexxIT/YandexStation/blob/master/custom_components/yandex_station/core/yandex_session.py
    2) https://github.com/MarshalX/yandex-music-token
    3) https://t.me/MarshalC/766

"""

import re
from aiohttp import ClientSession, ClientConnectorError


class YandexSession:
    """
    Класс для авторизации в Яндекс по логину и паролю для получения токена для ЯМ
    """

    class LoginResponse:
        """
        Класс для возвращаемого значения от Яндекс сессии
        """

        def __init__(self):
            self._resp = {"error": None, "token": None}

        def set_error(self, error: str):
            self._resp["error"] = error

        def set_token(self, token: str):
            self._resp["token"] = token

        def get_error(self):
            return self._resp["error"]

        def get_token(self):
            return self._resp["token"]

    def __init__(self, login: str, password: str):
        self._auth_payload: dict = {}
        self._session = ClientSession()
        self._xtoken = None
        self._login = login
        self._password = password
        self._login_response = YandexSession.LoginResponse()

    async def _login_username(self):
        """
        Первым шагом отправляется логин пользователя.
        Происходит проверка на существование аккаунта, возможность входа (есть ли ограничение),
        возможность регистрации нового аккаунта с таким логином при его отсутствии.

        Результатом первого шага является так называемый track id — это некий идентификатор сессии авторизации.
        """
        # csrf_token
        r = await self._session.get("https://passport.yandex.ru/am?app_platform=android")
        resp = await r.text()
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        self._auth_payload = {"csrf_token": m[1]}

        # track_id
        r = await self._session.post(
            "https://passport.yandex.ru/registration-validations/auth/multi_step/start",
            data={**self._auth_payload, "login": self._login}
        )
        resp = await r.json()
        if resp.get("can_register") is True:
            self._login_response.set_error("Аккаунт не найден!")
            return

        self._auth_payload["track_id"] = resp["track_id"]

    async def _login_password(self):
        """
        Вторым шагом происходит проверка аутентификатора.
        Отправляется запрос содержащий в себе пароль пользователя, который может быть OTP при включённой 2FA и
        непосредственно сам идентификатор с прошлого шага.

        При успешном выполнении запроса получаем большой объект с информацией об аккаунте
        (имя, логин, дата рождения, аватарка и прочее) и очень важный атрибут — X-Token.
        """

        r = await self._session.post(
            "https://passport.yandex.ru/registration-validations/auth/multi_step/commit_password",
            data={
                **self._auth_payload,
                "password": self._password,
                "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login"
            }
        )
        resp = await r.json()
        if resp["status"] != "ok":
            self._login_response.set_error("Не удалось авторизоваться!")
            return

        if "redirect_url" in resp:
            print(resp)
            self._login_response.set_error("Редирект не поддерживается!\n\n"
                                           "Попробуйте позже, либо самостоятельно введите токен.")
            return

        # x_token
        await self._login_cookies()

    async def _login_cookies(self):
        """
        В конце концов мы стучимся за токеном к определённому приложению.
        Стучимся с помощью нашего универсального X-Token’a, а в запросе указываем данные от необходимого нам приложения.
        """
        host = "passport.yandex.ru"

        cookies = "; ".join([
            f"{c.key}={c.value}" for c in self._session.cookie_jar
            if c["domain"].endswith("yandex.ru")
        ])

        r = await self._session.post(
            "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
            data={
                "client_id": "c0ebe342af7d48fbbbfcf2d2eedb8f9e",
                "client_secret": "ad0a908f0aa341a182a37ecd75bc319e",
            }, headers={
                "Ya-Client-Host": host,
                "Ya-Client-Cookie": cookies
            }
        )
        resp = await r.json()
        self._xtoken = resp["access_token"]

    async def get_music_token(self) -> LoginResponse:
        """
        Получаем токен ЯМ по X-токену
        """
        try:
            await self._login_username()
            if self._login_response.get_error() is None:
                await self._login_password()
                if self._login_response.get_error() is None:
                    payload = {
                        # Thanks to https://github.com/MarshalX/yandex-music-api/
                        'client_secret': '53bc75238f0c4d08a118e51fe9203300',
                        'client_id': '23cabbbdc6cd418abb4b39c32c41195d',
                        'grant_type': 'x-token',
                        'access_token': self._xtoken
                    }
                    r = await self._session.post(
                        'https://oauth.mobile.yandex.net/1/token', data=payload
                    )
                    resp = await r.json()
                    if 'access_token' in resp:
                        self._login_response.set_token(resp['access_token'])
                    else:
                        self._login_response.set_error('Не удалось получить токен!')
        except ClientConnectorError:
            self._login_response.set_error('Не удалось подключиться к Яндексу!\n\nПроверьте подключение к Интернету '
                                           'или попробуйте позже.')
        finally:
            await self._session.close()
            return self._login_response
