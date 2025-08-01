import pytest
import json
import hashlib
import datetime
from unittest.mock import Mock, patch
from redis.exceptions import ConnectionError, TimeoutError

import api
from store import Store


# Custom decorator for parametrized tests with clear test names
def cases(test_cases):
    """Decorator for parametrized tests with descriptive IDs"""

    def decorator(func):
        # Generate IDs for each test case
        ids = []
        for i, case in enumerate(test_cases):
            # Create descriptive ID from test case data
            parts = []
            if 'method' in case:
                parts.append(f"method={case['method']}")
            if 'login' in case:
                parts.append(f"login={case['login']}")
            if 'token' in case:
                parts.append(f"token={'<empty>' if case['token'] == '' else '<set>'}")
            if 'arguments' in case and case['arguments']:
                args_str = str(case['arguments'])[:30]
                parts.append(f"args={args_str}")

            ids.append(" | ".join(parts) if parts else f"case_{i}")

        return pytest.mark.parametrize("request_data", test_cases, ids=ids)(func)

    return decorator


class TestMethodRequest:
    """Unit tests for MethodRequest validation"""

    def test_valid_request(self):
        """Test valid method request"""
        data = {
            "account": "horns&hoofs",
            "login": "user",
            "token": "token123",
            "arguments": {"key": "value"},
            "method": "online_score"
        }
        request = api.MethodRequest(data)
        assert request.is_valid
        assert not request.errors

    def test_missing_required_fields(self):
        """Test request with missing required fields"""
        data = {"account": "test"}
        request = api.MethodRequest(data)
        assert not request.is_valid
        assert "login" in request.errors
        assert "token" in request.errors
        assert "arguments" in request.errors
        assert "method" in request.errors

    def test_empty_method_not_allowed(self):
        """Test that empty method is not allowed"""
        data = {
            "login": "user",
            "token": "token",
            "arguments": {},
            "method": ""
        }
        request = api.MethodRequest(data)
        assert not request.is_valid
        assert "method" in request.errors

    def test_is_admin_property(self):
        """Test is_admin property"""
        data = {
            "login": "admin",
            "token": "token",
            "arguments": {},
            "method": "online_score"
        }
        request = api.MethodRequest(data)
        assert request.is_admin

        data["login"] = "user"
        request = api.MethodRequest(data)
        assert not request.is_admin


class TestOnlineScoreRequest:
    """Unit tests for OnlineScoreRequest validation"""

    @cases([
        {"phone": "79175002040", "email": "test@example.com"},
        {"first_name": "John", "last_name": "Doe"},
        {"gender": 1, "birthday": "01.01.1990"},
    ])
    def test_valid_pairs(self, request_data):
        """Test valid field pairs"""
        request = api.OnlineScoreRequest(request_data)
        assert request.is_valid
        assert not request.errors

    @cases([
        {"phone": "79175002040"},
        {"email": "test@example.com"},
        {"first_name": "John"},
        {"last_name": "Doe"},
        {"gender": 1},
        {"birthday": "01.01.1990"},
        {},
    ])
    def test_invalid_incomplete_pairs(self, request_data):
        """Test incomplete field pairs"""
        request = api.OnlineScoreRequest(request_data)
        assert not request.is_valid
        assert "arguments" in request.errors

    def test_invalid_phone(self):
        """Test invalid phone numbers"""
        invalid_phones = [
            "89175002040",  # Not starting with 7
            "7917500204",  # Only 10 digits
            "791750020400",  # 12 digits
            "7917500204a",  # Contains letter
            "+79175002040",  # Contains +
        ]

        for phone in invalid_phones:
            request = api.OnlineScoreRequest({"phone": phone, "email": "test@test.com"})
            assert not request.is_valid
            assert "phone" in request.errors

    def test_invalid_email(self):
        """Test invalid emails"""
        request = api.OnlineScoreRequest({"email": "notanemail", "phone": "79175002040"})
        assert not request.is_valid
        assert "email" in request.errors

    def test_invalid_birthday(self):
        """Test invalid birthdays"""
        # More than 70 years ago
        request = api.OnlineScoreRequest({"birthday": "01.01.1900", "gender": 1})
        assert not request.is_valid
        assert "birthday" in request.errors

        # Invalid format
        request = api.OnlineScoreRequest({"birthday": "2000-01-01", "gender": 1})
        assert not request.is_valid
        assert "birthday" in request.errors

    def test_invalid_gender(self):
        """Test invalid gender values"""
        for gender in [-1, 3, "1", None]:
            request = api.OnlineScoreRequest({"gender": gender, "birthday": "01.01.1990"})
            assert not request.is_valid


class TestClientsInterestsRequest:
    """Unit tests for ClientsInterestsRequest validation"""

    def test_valid_request(self):
        """Test valid clients interests request"""
        request = api.ClientsInterestsRequest({"client_ids": [1, 2, 3]})
        assert request.is_valid
        assert not request.errors

    def test_with_date(self):
        """Test request with optional date field"""
        request = api.ClientsInterestsRequest({
            "client_ids": [1, 2, 3],
            "date": "01.01.2023"
        })
        assert request.is_valid

    def test_empty_client_ids(self):
        """Test empty client_ids list"""
        request = api.ClientsInterestsRequest({"client_ids": []})
        assert not request.is_valid
        assert "client_ids" in request.errors

    def test_invalid_client_ids(self):
        """Test invalid client_ids"""
        invalid_ids = [
            None,
            "not a list",
            [1, "2", 3],  # Mixed types
            [1.5, 2.5],  # Floats
        ]

        for ids in invalid_ids:
            request = api.ClientsInterestsRequest({"client_ids": ids})
            assert not request.is_valid


class TestAuthentication:
    """Unit tests for authentication"""

    def setup_method(self):
        """Setup for each test"""
        self.context = {}
        self.headers = {}
        self.store = Mock()

    def get_response(self, request):
        """Helper to get response"""
        return api.method_handler(
            {"body": request, "headers": self.headers},
            self.context,
            self.store
        )

    @cases([
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "", "arguments": {}},
        {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "token": "sdd", "arguments": {}},
        {"account": "horns&hoofs", "login": "admin", "method": "online_score", "token": "", "arguments": {}},
    ])
    def test_bad_auth(self, request_data):
        """Test invalid authentication"""
        response, code = self.get_response(request_data)
        assert code == api.FORBIDDEN

    def test_valid_auth(self):
        """Test valid authentication"""
        request = {
            "account": "horns&hoofs",
            "login": "h&f",
            "method": "online_score",
            "arguments": {"phone": "79175002040", "email": "test@test.com"}
        }
        # Calculate valid token
        request["token"] = hashlib.sha512(
            (request["account"] + request["login"] + api.SALT).encode('utf-8')
        ).hexdigest()

        response, code = self.get_response(request)
        assert code == api.OK

    def test_admin_auth(self):
        """Test admin authentication"""
        request = {
            "account": "horns&hoofs",
            "login": "admin",
            "method": "online_score",
            "arguments": {"phone": "79175002040", "email": "test@test.com"}
        }
        # Calculate admin token
        request["token"] = hashlib.sha512(
            (datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')
        ).hexdigest()

        response, code = self.get_response(request)
        assert code == api.OK
        assert response.get("score") == 42  # Admin always gets 42


class TestMethodHandler:
    """Integration tests for method_handler"""

    def setup_method(self):
        """Setup for each test"""
        self.context = {}
        self.headers = {}
        self.store = Mock()

    def get_response(self, request):
        """Helper to get response"""
        return api.method_handler(
            {"body": request, "headers": self.headers},
            self.context,
            self.store
        )

    def make_valid_auth_token(self, request):
        """Helper to create valid auth token"""
        if request.get("login") == api.ADMIN_LOGIN:
            return hashlib.sha512(
                (datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')
            ).hexdigest()
        return hashlib.sha512(
            (request["account"] + request["login"] + api.SALT).encode('utf-8')
        ).hexdigest()

    def test_empty_request(self):
        """Test empty request"""
        response, code = self.get_response({})
        assert code == api.INVALID_REQUEST

    def test_unknown_method(self):
        """Test unknown method"""
        request = {
            "account": "test",
            "login": "test",
            "method": "unknown_method",
            "arguments": {}
        }
        request["token"] = self.make_valid_auth_token(request)

        response, code = self.get_response(request)
        assert code == api.INVALID_REQUEST

    def test_invalid_arguments(self):
        """Test invalid arguments type"""
        request = {
            "account": "test",
            "login": "test",
            "method": "online_score",
            "arguments": "not a dict"
        }
        request["token"] = self.make_valid_auth_token(request)

        response, code = self.get_response(request)
        assert code == api.INVALID_REQUEST


class TestOnlineScoreHandler:
    """Integration tests for online_score handler"""

    def setup_method(self):
        """Setup for each test"""
        self.context = {}
        self.headers = {}
        self.store = Mock()
        self.store.cache_get.return_value = None
        self.store.cache_set.return_value = None

    def get_response(self, request):
        """Helper to get response"""
        return api.method_handler(
            {"body": request, "headers": self.headers},
            self.context,
            self.store
        )

    def make_valid_request(self, arguments, login="test"):
        """Helper to create valid request"""
        request = {
            "account": "test",
            "login": login,
            "method": "online_score",
            "arguments": arguments
        }
        if login == "admin":
            request["token"] = hashlib.sha512(
                (datetime.datetime.now().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode('utf-8')
            ).hexdigest()
        else:
            request["token"] = hashlib.sha512(
                (request["account"] + request["login"] + api.SALT).encode('utf-8')
            ).hexdigest()
        return request

    @cases([
        {"phone": "79175002040", "email": "test@test.com"},
        {"first_name": "John", "last_name": "Doe"},
        {"gender": 1, "birthday": "01.01.1990"},
        {"phone": "79175002040", "email": "test@test.com", "first_name": "John", "last_name": "Doe"},
    ])
    def test_valid_score_request(self, request_data):
        """Test valid score calculation"""
        request = self.make_valid_request(request_data)

        response, code = self.get_response(request)
        assert code == api.OK
        assert "score" in response
        assert isinstance(response["score"], (int, float))

        # Check context
        assert "has" in self.context
        assert set(self.context["has"]) >= set(request_data.keys())

    def test_admin_score(self):
        """Test admin always gets score 42"""
        arguments = {"phone": "79175002040", "email": "test@test.com"}
        request = self.make_valid_request(arguments, login="admin")

        response, code = self.get_response(request)
        assert code == api.OK
        assert response["score"] == 42

    def test_score_from_cache(self):
        """Test score retrieved from cache"""
        self.store.cache_get.return_value = "3.5"

        arguments = {"phone": "79175002040", "email": "test@test.com"}
        request = self.make_valid_request(arguments)

        response, code = self.get_response(request)
        assert code == api.OK
        assert response["score"] == 3.5

        # Verify cache was checked
        self.store.cache_get.assert_called_once()

    def test_score_cache_fail(self):
        """Test score calculation when cache fails"""
        self.store.cache_get.side_effect = Exception("Cache error")

        arguments = {"phone": "79175002040", "email": "test@test.com"}
        request = self.make_valid_request(arguments)

        response, code = self.get_response(request)
        assert code == api.OK
        assert "score" in response  # Should still calculate score


class TestClientsInterestsHandler:
    """Integration tests for clients_interests handler"""

    def setup_method(self):
        """Setup for each test"""
        self.context = {}
        self.headers = {}
        self.store = Mock()

    def get_response(self, request):
        """Helper to get response"""
        return api.method_handler(
            {"body": request, "headers": self.headers},
            self.context,
            self.store
        )

    def make_valid_request(self, arguments):
        """Helper to create valid request"""
        request = {
            "account": "test",
            "login": "test",
            "method": "clients_interests",
            "arguments": arguments
        }
        request["token"] = hashlib.sha512(
            (request["account"] + request["login"] + api.SALT).encode('utf-8')
        ).hexdigest()
        return request

    def test_valid_interests_request(self):
        """Test valid interests request"""
        self.store.get.return_value = json.dumps(["books", "movies"])

        arguments = {"client_ids": [1, 2, 3]}
        request = self.make_valid_request(arguments)

        response, code = self.get_response(request)
        assert code == api.OK
        assert len(response) == 3
        assert all(client_id in response for client_id in ["1", "2", "3"])

        # Check context
        assert self.context.get("nclients") == 3

    def test_interests_with_date(self):
        """Test interests request with date"""
        self.store.get.return_value = json.dumps(["travel", "sport"])

        arguments = {"client_ids": [1], "date": "01.01.2023"}
        request = self.make_valid_request(arguments)

        response, code = self.get_response(request)
        assert code == api.OK
        assert "1" in response

    def test_interests_store_failure(self):
        """Test interests when store fails"""
        self.store.get.side_effect = Exception("Store error")

        arguments = {"client_ids": [1, 2]}
        request = self.make_valid_request(arguments)

        # Should raise exception since get_interests needs store
        with pytest.raises(Exception):
            self.get_response(request)

    def test_interests_empty_store(self):
        """Test interests when store returns None"""
        self.store.get.return_value = None

        arguments = {"client_ids": [1]}
        request = self.make_valid_request(arguments)

        response, code = self.get_response(request)
        assert code == api.OK
        assert response["1"] == []


class TestStore:
    """Unit tests for Store class"""

    @patch('store.redis.ConnectionPool')
    @patch('store.redis.Redis')
    def test_store_initialization(self, mock_redis_class, mock_pool_class):
        """Test store initialization"""
        store = Store(host="localhost", port=6379)

        mock_pool_class.assert_called_once()
        assert store.retry_times == 3
        assert store.retry_delay == 0.1

    @patch('store.redis.Redis')
    def test_get_with_retry(self, mock_redis_class):
        """Test get operation with retry logic"""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        # First two calls fail, third succeeds
        mock_client.get.side_effect = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            "test_value"
        ]

        store = Store()
        result = store.get("test_key")

        assert result == "test_value"
        assert mock_client.get.call_count == 3

    @patch('store.redis.Redis')
    def test_get_all_retries_fail(self, mock_redis_class):
        """Test get operation when all retries fail"""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.side_effect = ConnectionError("Connection failed")

        store = Store()

        with pytest.raises(ConnectionError):
            store.get("test_key")

        assert mock_client.get.call_count == 3

    @patch('store.redis.Redis')
    def test_cache_get_failure_returns_none(self, mock_redis_class):
        """Test cache_get returns None on failure"""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.get.side_effect = ConnectionError("Connection failed")

        store = Store()
        result = store.cache_get("test_key")

        assert result is None
        assert mock_client.get.call_count == 3

    @patch('store.redis.Redis')
    def test_cache_set_failure_silently_fails(self, mock_redis_class):
        """Test cache_set silently fails"""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client
        mock_client.set.side_effect = ConnectionError("Connection failed")

        store = Store()
        # Should not raise exception
        store.cache_set("test_key", "test_value")

        assert mock_client.set.call_count == 3

    @patch('store.redis.Redis')
    def test_set_with_expire(self, mock_redis_class):
        """Test set operation with expiration"""
        mock_client = Mock()
        mock_redis_class.return_value = mock_client

        store = Store()
        store.set("test_key", "test_value", expire=3600)

        mock_client.set.assert_called_once_with("test_key", "test_value", ex=3600)


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
