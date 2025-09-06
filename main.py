"""
Main FastAPI application for the IntelliSpend expense tracker.
Handles API endpoints for managing users and expenses with user-sequential expense IDs.
Includes an endpoint to export all data as a CSV for Power BI.
"""
import sys
from datetime import datetime
from decimal import Decimal
import io
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# --- PRE-FLIGHT CHECK ---
try:
    import uvicorn
    import pandas as pd
except ImportError:
    print("\n--- FATAL ERROR ---")
    print("Required libraries are not installed.")
    print("Please run: pip install 'fastapi[all]' psycopg2-binary pandas python-dotenv")
    sys.exit(1)
print("✅ All required libraries are found.")


# --- DATABASE CONFIGURATION (INTEGRATED NEON DB) ---
# The connection string for your Neon cloud database is now used.
# It's recommended to store this in an environment variable for security.
DATABASE_URL = "postgresql://neondb_owner:npg_Xf06HpGKDlVJ@ep-wandering-snow-ad0y5szb-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"


# --- FASTAPI APP INITIALIZATION ---
app = FastAPI(
    title="IntelliSpend API",
    description="API for managing personal expenses and users, with Power BI integration.",
    version="1.4.0" # Updated version for cloud DB integration
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
    """Establishes and returns a database connection using the DATABASE_URL."""
    try:
        # psycopg2 can connect directly using the connection string.
        conn = psycopg2.connect(DATABASE_URL)
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
    Receives expense data, calculates the next user_expense_id for the user,
    and inserts it into the database.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COALESCE(MAX(user_expense_id), 0) FROM expenses WHERE user_id = %s;",
                (expense.user_id,)
            )
            max_id_row = cur.fetchone()
            max_id = max_id_row['coalesce'] if max_id_row else 0
            next_user_expense_id = max_id + 1

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

# --- Power BI Data Export Endpoint ---

@app.get("/expenses/powerbi_export", response_class=StreamingResponse)
def export_expenses_for_powerbi(conn=Depends(get_db_connection)):
    """
    Fetches all expense data, joins it with user data, converts it to a pandas DataFrame,
    and returns it as a CSV stream suitable for the Power BI Web data source.
    """
    try:
        sql_query = """
            SELECT
                e.user_expense_id,
                e.user_id,
                u.username,
                u.email,
                e.amount,
                e.category,
                e.merchant,
                e.transaction_date,
                e.source
            FROM
                expenses e
            LEFT JOIN
                users u ON e.user_id = u.user_id
            ORDER BY
                e.transaction_date DESC;
        """
        df = pd.read_sql_query(sql_query, conn)

        if df.empty:
             raise HTTPException(status_code=404, detail="No expense data found to export.")

        stream = io.StringIO()
        df.to_csv(stream, index=False)

        response = StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = "attachment; filename=intellispend_expenses.csv"

        return response

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            conn.close()

