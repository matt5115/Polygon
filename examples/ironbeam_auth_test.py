"""
Example script to test Ironbeam authentication.

This script demonstrates how to use the IronbeamAuth class to authenticate
with the Ironbeam API in both demo and live environments.
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from ironbeam_auth import get_ironbeam_token, IronbeamAuth

def test_direct_auth():
    """Test direct authentication using the module function."""
    print("🔐 Testing direct authentication...")
    try:
        token_info = get_ironbeam_token(environment="demo")
        print("✅ Authentication successful!")
        print(f"Environment: {token_info.get('environment')}")
        print(f"Token: {token_info.get('token')[:15]}...")
        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

def test_auth_class():
    """Test authentication using the IronbeamAuth class."""
    print("\n🔐 Testing IronbeamAuth class...")
    try:
        auth = IronbeamAuth(environment="demo")
        auth.authenticate()
        headers = auth.get_auth_headers()
        print("✅ Authentication successful!")
        print(f"Environment: {auth.environment}")
        print(f"Auth header: {headers['Authorization'][:30]}...")
        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Ironbeam Authentication Test\n")
    
    # Check if required environment variables are set
    required_vars = ["IRONBEAM_USERNAME", "IRONBEAM_PASSWORD", "IRONBEAM_OPERATOR"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("⚠️  The following required environment variables are not set:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease create a .env file or set these variables in your environment.")
        exit(1)
    
    # Run tests
    success = test_direct_auth()
    success &= test_auth_class()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed. Please check the output above.")
