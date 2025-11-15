# app/deps.py
import os
import logging
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import requests

load_dotenv()

try:
    from supabase import create_client
    HAS_SUPABASE_CLIENT = True
except Exception:
    create_client = None
    HAS_SUPABASE_CLIENT = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # Add this to your Render env vars

if not SUPABASE_URL:
    raise RuntimeError("Missing required environment variable SUPABASE_URL")
if not SUPABASE_SERVICE_ROLE_KEY:
    logger.warning("SUPABASE_SERVICE_ROLE_KEY not set")

def _mask(s: str | None):
    if not s:
        return None
    if len(s) <= 8:
        return "****"
    return s[:4] + "..." + s[-4:]

logger.info(f"SUPABASE_URL={SUPABASE_URL}")
logger.info(f"SUPABASE_KEY={_mask(SUPABASE_SERVICE_ROLE_KEY)}")
logger.info(f"JWT_SECRET configured: {bool(SUPABASE_JWT_SECRET)}")
logger.info(f"supabase client available: {HAS_SUPABASE_CLIENT}")

supabase = None
if HAS_SUPABASE_CLIENT and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info("Supabase client created successfully")
    except Exception as e:
        logger.exception("Failed to create Supabase client")
        supabase = None

bearer_scheme = HTTPBearer(auto_error=False)


def _verify_jwt_token(token: str):
    """
    Verify JWT token locally using the JWT secret.
    This is the most reliable method for production.
    """
    if not SUPABASE_JWT_SECRET:
        logger.warning("JWT_SECRET not configured, skipping JWT verification")
        return None
    
    try:
        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        logger.info(f"✅ JWT verified locally for user: {payload.get('sub')}")
        
        # Return user object in expected format
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "aud": payload.get("aud"),
            "role": payload.get("role"),
            **payload
        }
    except jwt.ExpiredSignatureError:
        logger.error("❌ JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ Invalid JWT token: {str(e)}")
        return None
    except Exception as e:
        logger.exception(f"❌ JWT verification error: {str(e)}")
        return None


def _verify_with_rest_endpoint(token: str):
    """
    Fallback: verify token with Supabase auth endpoint
    """
    endpoint = SUPABASE_URL.rstrip("/") + "/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY  # Important for REST calls
    }
    
    logger.info(f"🔍 REST verification at {endpoint}")
    
    try:
        r = requests.get(endpoint, headers=headers, timeout=10)
        logger.info(f"📡 REST status: {r.status_code}")
        
        if r.status_code == 200:
            user_data = r.json()
            logger.info(f"✅ User verified via REST: {user_data.get('id')}")
            return user_data
        else:
            logger.error(f"❌ REST failed: {r.status_code} - {r.text[:200]}")
            return None
    except Exception as e:
        logger.exception(f"❌ REST exception: {str(e)}")
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """
    Multi-method authentication:
    1. JWT verification (most reliable)
    2. REST endpoint verification
    """
    if credentials is None or not credentials.scheme or not credentials.credentials:
        logger.warning("❌ No authorization credentials")
        raise HTTPException(
            status_code=401, 
            detail="Missing Authorization header. Please sign in again."
        )

    token = credentials.credentials
    logger.info(f"🔐 Verifying token ({len(token)} chars)")

    user = None

    # Method 1: JWT verification (fastest and most reliable)
    if SUPABASE_JWT_SECRET:
        user = _verify_jwt_token(token)
        if user:
            return user

    # Method 2: REST endpoint
    logger.info("Trying REST verification...")
    user = _verify_with_rest_endpoint(token)
    
    if not user:
        logger.error("❌ All verification methods failed")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please sign in again."
        )

    logger.info(f"✅ User authenticated: {user.get('id')}")
    return user