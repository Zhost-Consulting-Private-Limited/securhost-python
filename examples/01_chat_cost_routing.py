import os
from securhost import SecurHostClient

api_key = os.environ.get("SECURHOST_API_KEY", "nxs_live_sample")
client = SecurHostClient(api_key=api_key)

reply = client.chat.complete(
    messages=[
        {"role": "system", "content": "You are a concise financial assistant."},
        {"role": "user", "content": "Calculate the annual compound growth rate from $10k to $25k over 5 years."}
    ],
    model="gpt-4o",
    request_type="general",
)

print("Response:\n", reply.output_text)
print("-" * 50)
print(f"Model Requested: gpt-4o")
print(f"Model Served:    {reply.model}")
print(f"Cost:            ${reply.cost.amount:.6f}")
print(f"Savings:         ${reply.cost.saved:.6f}")
