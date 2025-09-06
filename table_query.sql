-- -----------------------------------------------------------------
-- Table structure for `users`
-- -----------------------------------------------------------------
-- Stores user account information.
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE users IS 'Stores user account information.';
COMMENT ON COLUMN users.user_id IS 'Unique identifier for each user.';


-- -----------------------------------------------------------------
-- Table structure for `expenses`
-- -----------------------------------------------------------------
-- Stores individual expense records, linked to a user.
CREATE TABLE expenses (
    expense_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    merchant VARCHAR(100),
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(10) NOT NULL CHECK (source IN ('manual', 'sms'))
);

COMMENT ON TABLE expenses IS 'Stores individual expense records for each user.';
COMMENT ON COLUMN expenses.user_id IS 'Foreign key linking to the users table.';
COMMENT ON COLUMN expenses.source IS 'The method of data entry (e.g., manual, sms).';


-- -----------------------------------------------------------------
-- Sample Data Insertion
-- -----------------------------------------------------------------
-- Optional: Insert a sample user for development and testing purposes.
INSERT INTO users (username, email) VALUES ('testuser', 'test@example.com');

-- =================================================================
-- End of Script
-- =================================================================

