# Sample code for review gate testing
# This code has intentional issues for testing

def calculate_discount(price, discount_percent):
    """Calculate discounted price."""
    # Bug: No validation for negative values
    result = price - (price * discount_percent / 100)
    return result

def get_user_data(user_id):
    """Fetch user data from database."""
    # Security issue: SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    # Missing: actual database execution
    return query

def process_items(items):
    """Process list of items."""
    # Bug: Will crash if items is None
    for item in items:
        print(item.upper())

# Missing error handling
def divide(a, b):
    return a / b
