import os
from securhost import SecurHostClient

api_key = os.environ.get("SECURHOST_API_KEY", "nxs_live_sample")
client = SecurHostClient(api_key=api_key)

print("Streaming response:")
for chunk in client.chat.stream([{"role": "user", "content": "Write a 4-line poem about secure software."}]):
    print(chunk, end="", flush=True)
print()
