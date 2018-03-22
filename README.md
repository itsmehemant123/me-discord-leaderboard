## ME Leaderboard

### Setup

- Install dependencies with:

```bash
pip install -r requirements.txt
```

- Create `auth.json`, and place it inside the `config` folder. Its content should be:

```json
{
   "token": "<your_token>"
}
```

- Create `db.json`, and place it inside the `config` folder. Its content should be:

```json
{
  "database_uri": "mongodb://<uname>:<pwd>@<host>:<port>/<auth_db>",
}
```

### How to run

- Run the script with:

```bash
python client.py
```
