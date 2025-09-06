"""
Main FastAPI application for the IntelliSpend expense tracker.
Handles API endpoints for managing users and expenses with user-sequential expense IDs.
"""
import sys
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

# --- PRE-FLIGHT CHECK ---
try:
    import uvicorn
except ImportError:
    print("\n--- FATAL ERROR ---")
    print("Required libraries are not installed.")
    print("Please run: pip install 'fastapi[all]' psycopg2-binary")
    sys.exit(1)
print("✅ All required libraries are found.")


# --- DATABASE CONFIGURATION ---
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "intellispend_db"
DB_USER = "postgres"
DB_PASS = "Blackhole0galaxy" # Replace with your actual password


# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="IntelliSpend API",
    description="API for managing personal expenses and users.",
    version="1.2.0" # Updated version
)

# --- CORS MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins, including file:// for local HTML
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- DATABASE CONNECTION ---
def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ DATABASE CONNECTION FAILED: {e}")
        raise


# --- API MODELS (PYDANTIC) ---
class UserCreate(BaseModel):
    username: str
    email: str

class UserLogin(BaseModel):
    username: str
    email: str

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    created_at: datetime

class ExpenseCreate(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0, description="The amount spent, must be positive.")
    category: str
    merchant: str | None = None
    transaction_date: datetime | None = None

class ExpenseResponse(BaseModel):
    user_id: int
    user_expense_id: int
    amount: Decimal
    category: str
    merchant: str | None
    transaction_date: datetime
    source: str


# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the IntelliSpend API"}

# --- User Endpoints ---

@app.post("/users/signup", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, conn=Depends(get_db_connection)):
    """Creates a new user and stores them in the database."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql_query = """
                INSERT INTO users (username, email) VALUES (%s, %s)
                RETURNING user_id, username, email, created_at;
            """
            cur.execute(sql_query, (user.username, user.email))
            new_user = cur.fetchone()
            conn.commit()
            return new_user
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="A user with this username or email already exists.")
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

@app.post("/users/login", response_model=UserResponse)
def login_user(user: UserLogin, conn=Depends(get_db_connection)):
    """Authenticates a user by checking their credentials against the database."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql_query = "SELECT user_id, username, email, created_at FROM users WHERE username = %s AND email = %s;"
            cur.execute(sql_query, (user.username, user.email))
            db_user = cur.fetchone()
            if not db_user:
                raise HTTPException(status_code=401, detail="Invalid username or email.")
            return db_user
    except psycopg2.Error as e:
        raise HTTPException(status_code=400, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()


# --- Expense Endpoints ---

@app.post("/expenses/manual/", response_model=ExpenseResponse, status_code=201)
def create_manual_expense(expense: ExpenseCreate, conn=Depends(get_db_connection)):
    """
    Receives expense data, calculates the next user_expense_id within a transaction,
    and inserts it into the database.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get the current maximum user_expense_id for this specific user.
            cur.execute(
                "SELECT COALESCE(MAX(user_expense_id), 0) FROM expenses WHERE user_id = %s;",
                (expense.user_id,)
            )
            max_id = cur.fetchone()['coalesce']
            next_user_expense_id = max_id + 1

            # Insert the new expense with the calculated sequential ID.
            transaction_ts = expense.transaction_date or datetime.now()
            sql_query = """
                INSERT INTO expenses (user_id, user_expense_id, amount, category, merchant, transaction_date, source)
                VALUES (%s, %s, %s, %s, %s, %s, 'manual')
                RETURNING *;
            """
            cur.execute(sql_query, (
                expense.user_id,
                next_user_expense_id,
                expense.amount,
                expense.category,
                expense.merchant,
                transaction_ts
            ))
            new_expense = cur.fetchone()
            conn.commit()
            return new_expense
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

@app.get("/expenses/{user_id}", response_model=list[ExpenseResponse])
def get_user_expenses(user_id: int, conn=Depends(get_db_connection)):
    """Fetches all expenses for a specific user, ordered by their sequential ID."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql_query = "SELECT * FROM expenses WHERE user_id = %s ORDER BY user_expense_id DESC;"
            cur.execute(sql_query, (user_id,))
            expenses = cur.fetchall()
            return expenses
    except psycopg2.Error as e:
        raise HTTPException(status_code=400, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

