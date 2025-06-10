"""
Ironbeam Authentication Module

Handles authentication with Ironbeam's API for both demo and live environments.
"""
import os
import requests
from typing import Dict, Optional, Literal
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# API endpoints for different environments
IRONBEAM_API_HOSTS = {
    "demo": "https://demoapi.ironbeam.com",
    "live": "https://api.ironbeam.com"
}

def get_ironbeam_token(
    username: str = None,
    password: str = None,
    operator: str = None,
    environment: Literal["demo", "live"] = "demo"
) -> Dict[str, str]:
    """
    Authenticate with Ironbeam API and retrieve an access token.

    Args:
        username: Ironbeam username (or use IRONBEAM_USERNAME env var)
        password: Ironbeam password (or use IRONBEAM_PASSWORD env var)
        operator: Ironbeam operator code (or use IRONBEAM_OPERATOR env var)
        environment: API environment - 'demo' or 'live' (default: 'demo')

    Returns:
        Dict containing 'token' and 'base_url' if successful

    Raises:
        ValueError: If required credentials are missing
        Exception: If authentication fails
    """
    # Use provided credentials or fall back to environment variables
    username = username or os.getenv("IRONBEAM_USERNAME")
    password = password or os.getenv("IRONBEAM_PASSWORD")
    operator = operator or os.getenv("IRONBEAM_OPERATOR")
    
    # Validate required parameters
    if not all([username, password, operator]):
        raise ValueError(
            "Missing required credentials. Provide username, password, and operator "
            "or set IRONBEAM_USERNAME, IRONBEAM_PASSWORD, and IRONBEAM_OPERATOR "
            "environment variables."
        )
    
    # Get the appropriate base URL
    base_url = IRONBEAM_API_HOSTS.get(environment)
    if not base_url:
        raise ValueError(f"Invalid environment: {environment}. Must be 'demo' or 'live'.")
    
    # Prepare authentication request
    auth_url = f"{base_url}/api-token-auth/"
    payload = {
        "username": username,
        "password": password,
        "operator": operator
    }
    
    # Make the authentication request
    try:
        response = requests.post(auth_url, json=payload, timeout=10)
        response.raise_for_status()
        
        token = response.json().get("token")
        if not token:
            raise Exception("No token received in authentication response")
            
        return {
            "token": token,
            "base_url": base_url,
            "environment": environment,
            "expires_in": 3600  # Default token expiration (1 hour)
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Ironbeam authentication failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" - {e.response.status_code}: {e.response.text}"
        raise Exception(error_msg)


class IronbeamAuth:
    """
    A class to manage Ironbeam authentication and token refresh.
    """
    
    def __init__(self, username: str = None, password: str = None, operator: str = None, 
                 environment: str = "demo"):
        """
        Initialize the Ironbeam authentication handler.
        
        Args:
            username: Ironbeam username
            password: Ironbeam password
            operator: Ironbeam operator code
            environment: 'demo' or 'live' (default: 'demo')
        """
        self.username = username or os.getenv("IRONBEAM_USERNAME")
        self.password = password or os.getenv("IRONBEAM_PASSWORD")
        self.operator = operator or os.getenv("IRONBEAM_OPERATOR")
        self.environment = environment or os.getenv("IRONBEAM_ENV", "demo")
        self.token_info = None
    
    def authenticate(self) -> Dict[str, str]:
        """
        Authenticate with Ironbeam and store the token information.
        
        Returns:
            Dict containing token information
        """
        self.token_info = get_ironbeam_token(
            username=self.username,
            password=self.password,
            operator=self.operator,
            environment=self.environment
        )
        return self.token_info
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dict containing the Authorization header
            
        Raises:
            Exception: If not authenticated
        """
        if not self.token_info or 'token' not in self.token_info:
            raise Exception("Not authenticated. Call authenticate() first.")
            
        return {
            "Authorization": f"Token {self.token_info['token']}",
            "Content-Type": "application/json"
        }
