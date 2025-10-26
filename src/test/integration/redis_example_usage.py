#!/usr/bin/env python3
"""
Example usage of the RedisClient
"""
import os
from src.client import get_redis_client

# Using the specific Redis URL you provided
redis_url = "rediss://default:AUGJAAIncDI3YjVhYTZhNzRlNzI0YjEwYTY2ZGU2MTkwY2EzNzJlZHAyMTY3Nzc@unified-ape-16777.upstash.io:6379"

def main():
    # Create Redis client with your specific URL
    client = get_redis_client(redis_url)

    try:
        # Test basic operations
        print("Testing Redis operations...")

        # Set a value
        result = client.set('foo', 'bar')
        print(f"SET 'foo' = 'bar': {result}")

        # Get the value
        value = client.get('foo')
        print(f"GET 'foo': {value}")

        # Test with expiration
        client.set('temp_key', 'temp_value', ex=60)  # Expires in 60 seconds
        print(f"SET 'temp_key' with 60s expiration")

        # Check if key exists
        exists = client.exists('foo')
        print(f"EXISTS 'foo': {exists}")

        # Test increment
        client.set('counter', '0')
        new_value = client.incr('counter')
        print(f"INCR 'counter': {new_value}")

        # Get all keys (be careful with this in production!)
        keys = client.keys('*')
        print(f"All keys: {keys}")

        # Clean up
        client.delete('foo', 'temp_key', 'counter')
        print("Cleaned up test keys")

        print("All operations completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()