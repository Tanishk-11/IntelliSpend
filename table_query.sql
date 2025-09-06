-- First, create the 'users' table since the 'expenses' table will reference it.
-- This table will store user information.
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Now, create the 'expenses' table with a reference to the 'users' table.
CREATE TABLE expenses (
    -- expense_id: Unique identifier for each expense, automatically increments.
    expense_id SERIAL PRIMARY KEY,

    -- user_id: Links this expense to a user in the 'users' table.
    -- Ensures an expense cannot exist without a valid user.
    user_id INTEGER NOT NULL REFERENCES users(user_id),

    -- amount: The cost of the expense. DECIMAL is used for financial accuracy.
    amount DECIMAL(10, 2) NOT NULL,

    -- category: The user-defined category for the expense (e.g., 'Food', 'Transport').
    category VARCHAR(50) NOT NULL,

    -- merchant: The name of the vendor or store where the purchase was made. Can be empty.
    merchant VARCHAR(100),

    -- transaction_date: The exact date and time of the expense. Defaults to now.
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- source: How the data was entered. The CHECK constraint ensures data integrity.
    source VARCHAR(10) NOT NULL CHECK (source IN ('manual', 'sms'))
);
