# Scoring API

HTTP API service for online scoring and client interests retrieval with Redis-based caching.

## Features

- Online scoring based on user attributes
- Client interests retrieval
- Redis-based caching with retry logic
- Comprehensive test coverage using pytest

## Requirements

- Python 3.10
- Redis server
- UV package manager

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ka4en3/scoring-api.git
cd scoring-api
```

2. Install UV (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  
uv pip install -e ".[dev]"
```

## Configuration

### Redis Configuration

The Store class accepts the following parameters:
- `host`: Redis host (default: 'localhost')
- `port`: Redis port (default: 6379)
- `db`: Redis database number (default: 0)
- `socket_connect_timeout`: Connection timeout in seconds (default: 5)
- `socket_timeout`: Socket timeout in seconds (default: 5)
- `retry_times`: Number of retry attempts (default: 3)
- `retry_delay`: Delay between retries in seconds (default: 0.1)

## Usage

### Starting Redis
```bash 
# if Redis installed locally
redis-server

# Using Docker
docker run -d -p 6379:6379 --name redis redis:latest
```

### Starting the API Server

```bash
python api.py --port 8080 --log api.log
```

### API Endpoints

#### Online Score

Calculate online score based on user attributes.

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
```powershell
Invoke-WebRequest -Method POST -Uri "http://127.0.0.1:8080/method/" -ContentType "application/json" -Body '{"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd5a08f21fc95", "arguments": {"phone": "79175002040", "email": "john@doe.ru", "first_name": "John", "last_name": "Doe", "birthday": "01.01.1990", "gender": 1}}'
```

**Response:**
```json
{"response": {"score": 5.0}, "code": 200}
```

#### Clients Interests

Get interests for specified clients.

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
  "response": {
    "1": ["books", "hi-tech"],
    "2": ["pets", "tv"],
    "3": ["travel", "music"],
    "4": ["cinema", "geek"]
  },
  "code": 200
}
```

### Authentication

The API uses token-based authentication. Tokens are generated using SHA512 hash:
- Regular users: `SHA512(account + login + SALT)`
- Admin users: `SHA512(current_hour + ADMIN_SALT)`

## Testing

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

### Run specific test file
```bash
pytest test_api.py -v
```

### Run specific test class
```bash
pytest test_api.py::TestOnlineScoreHandler -v
```

### Run tests matching pattern
```bash
pytest -k "test_valid" -v
```

## Development

### Project Structure

```
scoring-api/
├── api.py             # Main API implementation
├── scoring.py         # Scoring logic
├── store.py           # Redis store implementation
├── test_api.py        # Test suite
├── pyproject.toml     # Project configuration
└── README.md          # This file
```

## Error Handling

The API returns appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 403: Forbidden (authentication failed)
- 422: Invalid Request (validation failed)
- 500: Internal Server Error

## License

MIT License