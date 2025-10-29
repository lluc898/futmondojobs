import requests

session = requests.Session()

HEADERS = {
    "Origin": "https://app.futmondo.com",
    "Referer": "https://app.futmondo.com/",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "es-ES,es;q=0.9",
    "X-Requested-With": "com.futmondo.app",
    "X-Device": "android",
    "Host": "api.futmondo.com",
    "Connection": "keep-alive",
}
