#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Full implementation of Scoring API with declarative field validation

import abc
import json
import datetime
import logging
import hashlib
import uuid
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer

import scoring
from store import Store

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class ValidationError(Exception):
    """Custom exception for field validation errors"""
    pass


class Field:
    """Base field class with common validation logic"""

    def __init__(self, required=False, nullable=False):
        self.required = required
        self.nullable = nullable
        self.field_name = None  # Will be set by metaclass

    def __set_name__(self, owner, name):
        """Called when field is assigned to a class attribute"""
        self.field_name = name

    def validate(self, value):
        """Base validation method"""
        if value is None:
            if self.required:
                raise ValidationError(f"{self.field_name} is required")
            return

        if not self.nullable and not value:
            raise ValidationError(f"{self.field_name} cannot be empty")

    def clean(self, value):
        """Override this method for custom field validation"""
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.field_name)

    def __set__(self, instance, value):
        self.validate(value)
        cleaned_value = self.clean(value)
        instance.__dict__[self.field_name] = cleaned_value


class CharField(Field):
    """String field"""

    def clean(self, value):
        if value is not None and not isinstance(value, str):
            raise ValidationError(f"{self.field_name} must be a string")
        return value


class ArgumentsField(Field):
    """Dictionary field for arguments"""

    def clean(self, value):
        if value is not None and not isinstance(value, dict):
            raise ValidationError(f"{self.field_name} must be a dictionary")
        return value


class EmailField(CharField):
    """Email field with @ validation"""

    def clean(self, value):
        value = super().clean(value)
        if value and '@' not in value:
            raise ValidationError(f"{self.field_name} must contain @")
        return value


class PhoneField(Field):
    """Phone field - 11 digits starting with 7"""

    def clean(self, value):
        if value is None:
            return value

        # Convert to string for validation
        phone_str = str(value)

        if not phone_str.isdigit():
            raise ValidationError(f"{self.field_name} must contain only digits")

        if len(phone_str) != 11:
            raise ValidationError(f"{self.field_name} must be 11 digits long")

        if not phone_str.startswith('7'):
            raise ValidationError(f"{self.field_name} must start with 7")

        return phone_str
        # return value


class DateField(Field):
    """Date field in DD.MM.YYYY format"""

    def clean(self, value):
        if value is None:
            return value

        if not isinstance(value, str):
            raise ValidationError(f"{self.field_name} must be a string")

        try:
            datetime.datetime.strptime(value, '%d.%m.%Y')
        except ValueError:
            raise ValidationError(f"{self.field_name} must be in DD.MM.YYYY format")

        return value


class BirthDayField(DateField):
    """Birthday field - not more than 70 years ago"""

    def clean(self, value):
        value = super().clean(value)
        if value is None:
            return value

        birth_date = datetime.datetime.strptime(value, '%d.%m.%Y')
        today = datetime.datetime.today()
        age = (today - birth_date).days / 365.25

        if age > 70:
            raise ValidationError(f"{self.field_name} cannot be more than 70 years ago")

        return birth_date
        # return value


class GenderField(Field):
    """Gender field - 0, 1 or 2"""

    def clean(self, value):
        if value is None:
            return value

        if value not in [0, 1, 2]:
            raise ValidationError(f"{self.field_name} must be 0, 1 or 2")

        return value


class ClientIDsField(Field):
    """List of client IDs"""

    def clean(self, value):
        if value is None:
            return value

        if not isinstance(value, list):
            raise ValidationError(f"{self.field_name} must be a list")

        if not value and self.required:
            raise ValidationError(f"{self.field_name} cannot be empty")

        for item in value:
            if not isinstance(item, int):
                raise ValidationError(f"{self.field_name} must contain only integers")

        return value


class RequestMeta(type):
    """Metaclass that collects all Field instances"""

    def __new__(mcs, name, bases, namespace):
        fields = {}

        # Collect fields from base classes
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)

        # Collect fields from current class
        for key, value in namespace.items():
            if isinstance(value, Field):
                fields[key] = value

        cls = super().__new__(mcs, name, bases, namespace)
        cls._fields = fields
        return cls


class Request(metaclass=RequestMeta):
    """Base request class with validation"""

    def __init__(self, data):
        self.errors = {}
        self.data = data or {}
        self._parse_request()

    def _parse_request(self):
        """Parse request data and set field values"""
        for field_name, field in self._fields.items():
            value = self.data.get(field_name)
            try:
                setattr(self, field_name, value)
            except ValidationError as e:
                self.errors[field_name] = str(e)

    def validate(self) -> bool:
        """Validate all fields and request logic"""
        return not self.errors

    @property
    def is_valid(self) -> bool:
        """Check if request is valid"""
        return self.validate()


class MethodRequest(Request):
    """Main method request"""

    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self) -> bool:
        return self.login == ADMIN_LOGIN


class OnlineScoreRequest(Request):
    """Request for online_score method"""

    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def validate(self):
        """Check that at least one pair of fields is not empty"""
        if self.errors:
            return False

        pairs = [
            (self.phone, self.email),
            (self.first_name, self.last_name),
            (self.gender, self.birthday)
        ]

        # Check if at least one pair has both non-empty values
        has_pair = any(
            all(v is not None and v != '' for v in pair)
            for pair in pairs
        )

        if not has_pair:
            self.errors['arguments'] = (
                "At least one pair must be present with non-empty values: "
                "phone-email, first_name-last_name, or gender-birthday"
            )

        return not self.errors


class ClientsInterestsRequest(Request):
    """Request for clients_interests method"""

    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


def method_handler(request, ctx, store) -> (dict, int):
    """Main method handler"""
    handlers = {
        "online_score": online_score_handler,
        "clients_interests": clients_interests_handler
    }

    # Parse main request
    method_request = MethodRequest(request['body'])

    if not method_request.is_valid:
        return method_request.errors, INVALID_REQUEST

    # Check authentication
    if not check_auth(method_request):
        return None, FORBIDDEN

    # Check if method exists
    if method_request.method not in handlers:
        return f"Unknown method: {method_request.method}", INVALID_REQUEST

    # Call appropriate handler
    return handlers[method_request.method](method_request, ctx, store)


def online_score_handler(request, ctx, store) -> (dict, int):
    """Handler for online_score method"""
    score_request = OnlineScoreRequest(request.arguments)

    if not score_request.is_valid:
        return score_request.errors, INVALID_REQUEST

    # Add non-empty fields to context
    ctx['has'] = [
        field_name for field_name, field in score_request._fields.items()
        if getattr(score_request, field_name) is not None and getattr(score_request, field_name) != ''
    ]

    # Return 42 for admin, otherwise calculate score
    if request.is_admin:
        score = 42
    else:
        score = scoring.get_score(
            store,
            score_request.phone,
            score_request.email,
            score_request.birthday,
            score_request.gender,
            score_request.first_name,
            score_request.last_name
        )

    return {"score": score}, OK


def clients_interests_handler(request, ctx, store) -> (dict, int):
    """Handler for clients_interests method"""
    interests_request = ClientsInterestsRequest(request.arguments)

    if not interests_request.is_valid:
        return interests_request.errors, INVALID_REQUEST

    # Add number of clients to context
    ctx['nclients'] = len(interests_request.client_ids)

    # Get interests for each client
    interests = {}
    for client_id in interests_request.client_ids:
        interests[str(client_id)] = scoring.get_interests(store, client_id)

    return interests, OK


def check_auth(request) -> bool:
    """Check authentication"""
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT).encode('utf-8')).hexdigest()
    return digest == request.token


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = Store()

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            # data_string_decoded = data_string.decode('utf-8')  # Decode bytes to UTF-8 string
            data_string_decoded = data_string
            request = json.loads(data_string_decoded)
        except Exception as e:
            logging.exception("Request error: %s" % e)
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string_decoded, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(filename=args.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", args.port), MainHTTPHandler)
    logging.info("Starting server at %s" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
