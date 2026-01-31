"""
API client with security and performance issues
"""

import requests
import json
import time


class APIClient:
    def __init__(self, api_key):
        # Bug: Storing credentials in plain text
        self.api_key = api_key
        self.base_url = "http://api.example.com"  # Bug: Using HTTP instead of HTTPS
        
    def get_user_data(self, user_id):
        # Bug: No input validation
        # Bug: String concatenation for URL (SQL injection equivalent)
        url = self.base_url + "/users/" + user_id
        
        # Bug: No timeout
        response = requests.get(url)
        
        # Bug: No status code check
        data = response.json()
        
        return data
    
    def fetch_all_users(self, user_ids):
        # Bug: N+1 query problem - should batch
        users = []
        for uid in user_ids:
            time.sleep(0.1)  # Bug: Unnecessary sleep in loop
            users.append(self.get_user_data(uid))
        
        return users
    
    def save_to_file(self, data, filename):
        # Bug: Potential path traversal vulnerability
        with open(filename, 'w') as f:
            # Bug: Not handling JSON serialization errors
            f.write(json.dumps(data))
    
    def authenticate(self, username, password):
        # Bug: Sending credentials in GET request
        # Bug: Password in URL
        url = f"{self.base_url}/login?user={username}&pass={password}"
        
        response = requests.get(url, verify=False)  # Bug: Disabled SSL verification
        
        return response


# Bug: Hardcoded credentials
API_KEY = "sk-1234567890abcdef"
SECRET = "my-secret-key"


def fetch_data():
    client = APIClient(API_KEY)
    
    # Bug: Infinite recursion risk
    def recursive_fetch(depth):
        if depth > 0:
            return recursive_fetch(depth + 1)  # Bug: depth increases instead of decreases
    
    recursive_fetch(1)


# Bug: Resource leak - connection never closed
def download_file(url):
    response = requests.get(url, stream=True)
    data = response.content
    # Bug: Response not closed
    return data


# Bug: Race condition
counter = 0

def increment():
    global counter
    temp = counter
    # Bug: Non-atomic operation
    time.sleep(0.001)
    counter = temp + 1
