# Streamlit Community Cloud Secrets

Open **Streamlit Community Cloud → App → Settings / Manage app → Secrets** and paste TOML with these keys:

```toml
[snowflake]
account = "YOUR_ACCOUNT_IDENTIFIER"
user = "YOUR_USER"
password = "YOUR_PASSWORD"
warehouse = "YOUR_WAREHOUSE"
database = "CUSTOMERPULSE_DB"
schema = "APP"
role = "YOUR_ROLE"
```

Save the secrets and reboot the app. A successful connection and `CUSTOMER_360` query change the app badge to **🟢 Live Snowflake**. The AI badge appears only after both `AI_SENTIMENT` and an account-supported `AI_COMPLETE` model pass live capability probes.

Streamlit Community Cloud does **not** automatically receive the developer's local `~/.snowflake/connections.toml`. Add the connection values through the app's Secrets screen; never commit `.streamlit/secrets.toml`.

For key-pair authentication, replace `password` with `authenticator = "SNOWFLAKE_JWT"`, `private_key_file`, and—only when required—`private_key_file_pwd`. The key file must be supplied securely by the deployment environment and must not be committed.
