#!/usr/bin/env python3
"""
Database initialization script
Run this to set up the database for the first time
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import init_db, reset_db, DATABASE_URL
from src.models import Base


def main():
    """Initialize the database"""
    print("=" * 60)
    print("AI-Scheduler Database Initialization")
    print("=" * 60)
    print(f"\nDatabase URL: {DATABASE_URL}")
    print("\nThis will create all necessary tables.")
    
    response = input("\nContinue? (y/n): ")
    if response.lower() != 'y':
        print("Initialization cancelled.")
        return
    
    try:
        init_db()
        print("\n✓ Database initialized successfully!")
        print("\nCreated tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
        
        print("\nNext steps:")
        print("1. Make sure your .env file has your Google API key")
        print("2. Run the server: uvicorn src.main:app --reload")
        print("3. Visit http://localhost:8000/docs for API documentation")
        
    except Exception as e:
        print(f"\n✗ Error initializing database: {str(e)}")
        sys.exit(1)


def reset():
    """Reset the database (WARNING: This will delete all data!)"""
    print("=" * 60)
    print("WARNING: DATABASE RESET")
    print("=" * 60)
    print("\nThis will DELETE ALL DATA and recreate all tables!")
    print(f"Database: {DATABASE_URL}")
    
    response = input("\nAre you ABSOLUTELY sure? Type 'RESET' to confirm: ")
    if response != 'RESET':
        print("Reset cancelled.")
        return
    
    try:
        reset_db()
        print("\n✓ Database reset successfully!")
        
    except Exception as e:
        print(f"\n✗ Error resetting database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset()
    else:
        main()