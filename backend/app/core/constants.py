# User Roles
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_MODERATOR = "moderator"

# Password Hashing Constants
PASSWORD_MIN_LENGTH = 8

# Rate Limit Configs (Requests per Minute)
RATE_LIMIT_DEFAULT_LIMIT = 60
RATE_LIMIT_AUTH_LIMIT = 10

# API Response Messages
MSG_USER_NOT_FOUND = "User not found."
MSG_EMAIL_TAKEN = "Email already registered."
MSG_INCORRECT_CREDENTIALS = "Incorrect email or password."
MSG_INACTIVE_USER = "Inactive user account."
MSG_UNAUTHORIZED = "Not authenticated."
MSG_FORBIDDEN = "Forbidden. Insufficient permissions."
