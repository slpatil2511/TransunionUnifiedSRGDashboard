import requests

url = "https://transunion-dev-restapi.onbmc.com/api/jwt/login"

payload = {
    "username": "saris",
    "password": "321"
}

response = requests.post(
    url,
    data=payload,
    verify=False
)

print(response.status_code)
print(response.text)