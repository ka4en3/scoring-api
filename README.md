
# Scoring API

An HTTP API service for scoring user data.

## Installation

### Using UV (recommended)

```bash
# Install UV
pip install uv

# Create virtual environment
uv venv

# Activate
source .venv/bin/activate

# Install dependencies
uv pip install .
```

## Running the API

### Start the server

```bash
# Start on default port (8080)
python api.py

# Start on a different port
python api.py -p 8081

# Start with logging to a file
python api.py -l api.log
```

### Run tests

```bash
python test.py
```

## API Methods

### `online_score`

Calculates a user's scoring score.

**Request:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "account": "horns&hoofs",
  "login": "h&f",
  "method": "online_score",
  "token": "55cc...fc95",
  "arguments": {
    "phone": "79175002040",
    "email": "doe@gmail.com",
    "first_name": "John",
    "last_name": "Doe",
    "birthday": "01.01.1990",
    "gender": 1
  }
}' http://127.0.0.1:8080/method/
```

**Response:**
```json
{"code": 200, "response": {"score": 5.0}}
```

---

### `clients_interests`

Returns a list of interests for the specified client IDs.

**Request:**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "account": "horns&hoofs",
  "login": "h&f",
  "method": "clients_interests",
  "token": "55cc...fc95",
  "arguments": {
    "client_ids": [1, 2, 3, 4],
    "date": "20.07.2017"
  }
}' http://127.0.0.1:8080/method/
```

**Response:**
```json
{
  "code": 200,
  "response": {
    "1": ["books", "hi-tech"],
    "2": ["pets", "tv"],
    "3": ["travel", "music"],
    "4": ["cinema", "geek"]
  }
}
```

## Project Structure

```
scoring-api/
├── api.py           # Main API file with validation
├── scoring.py       # Scoring logic
├── test.py          # Tests
├── pyproject.toml   # Dependencies and project metadata
└── README.md        # Readme
```

## Authentication

For regular users, the token is calculated as:
```
SHA512(account + login + SALT)
```

For admin:
```
SHA512(current_hour + ADMIN_SALT)
```