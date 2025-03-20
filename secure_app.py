from flask import Flask, request, render_template, redirect, url_for, session
import MySQLdb
import MySQLdb.cursors  # Import cursor types

app = Flask(__name__)
app.secret_key = '%MJhy2I4N@4k'  # Required for session management

def get_db_connection():
    return MySQLdb.connect(
        host="127.0.0.1",
        user="root",
        password="root",
        database="bank",
        autocommit=True,
        cursorclass=MySQLdb.cursors.DictCursor
    )

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password TEXT NOT NULL, 
            balance DECIMAL(10,2) NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute("INSERT IGNORE INTO users (id, username, password, balance) VALUES (1, 'admin', 'password123', 5000.00)")
    c.execute("INSERT IGNORE INTO users (id, username, password, balance) VALUES (2, 'brian', 'letmein', 100.00)")
    
    conn.commit()
    conn.close()

init_db()

# secure login route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_db_connection()
        c = conn.cursor()

        query = "SELECT * FROM users WHERE username = %s AND password = %s" # secure user input is never directly concatenated into sql
        c.execute(query, (username, password)) # uses execute(query, (username, password)) instead of formatting strings.
        user = c.fetchone()
        
        conn.close()
        
        if user:
            session['username'] = user['username']
            return redirect(url_for('account_dashboard', username=user['username']))
        else:
            return render_template('login.html', message="Invalid Credentials")
    
    return render_template('login.html', message="")

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/account/<username>', methods=['GET', 'POST'])
def account_dashboard(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))

    conn = get_db_connection()
    c = conn.cursor()

    # Get user info securely
    c.execute("SELECT username, balance FROM users WHERE username = %s", (username,))
    user = c.fetchone()

    # Get transaction history securely
    if username == 'admin':
        #  Admin sees ALL transactions
        c.execute("SELECT sender, recipient, amount, timestamp FROM transactions ORDER BY timestamp DESC")
    else:
        # Regular users see only their transactions
        c.execute("SELECT sender, recipient, amount, timestamp FROM transactions WHERE sender = %s OR recipient = %s ORDER BY timestamp DESC", (username, username))

    transactions = c.fetchall()

    users = []
    if username == 'admin':
        c.execute("SELECT username, balance FROM users")
        users = c.fetchall()

    conn.close()

    message = ""

    if request.method == 'POST':
        recipient = request.form.get('recipient')
        sender = request.form.get('sender') if username == 'admin' else username  # Admin selects sender, else default to user
        amount = request.form.get('amount')

        try:
            amount = float(amount)
            if amount <= 0:
                message = "Transaction amount must be positive!"
            elif recipient and sender:
                conn = get_db_connection()
                c = conn.cursor()

                # Ensure sender exists and has enough balance
                c.execute("SELECT balance FROM users WHERE username = %s", (sender,))
                sender_balance = c.fetchone()

                if sender_balance and sender_balance["balance"] >= amount:
                    # Update balances
                    c.execute("UPDATE users SET balance = balance - %s WHERE username = %s", (amount, sender))
                    c.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, recipient))
                    conn.commit()
                    # Insert transaction record
                    c.execute("INSERT INTO transactions (sender, recipient, amount) VALUES (%s, %s, %s)", (sender, recipient, amount))
                    conn.commit()

                else:
                    message = "Insufficient funds!"

                conn.close()
                return redirect(url_for('account_dashboard', username=username))
        except ValueError:
            message = "Invalid transaction amount!"

    return render_template('account.html', user=user, transactions=transactions, users=users, message=message)

# Secure Account Creation Route
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    message = ""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_db_connection()
        c = conn.cursor()

        # Allows SQL injection to check for existing users
        c.execute(f"SELECT * FROM users WHERE username = %s", (username,))
        existing_user = c.fetchone()

        if existing_user:
            message = "Username already taken!"
        else:
            # No input sanitization. SQL injection is possible.
            query = f"INSERT INTO users (username, password, balance) VALUES (%s, %s, 100.00)"
            c.execute(query,(username, password))
            conn.commit()
            message = "Account created successfully!"
        
        conn.close()
    
    return render_template('create_account.html', message=message)

@app.route('/reset_transactions', methods=['POST'])
def reset_transactions():
    # verify if is admin
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()

    # This will delete all transactions
    c.execute("DELETE FROM transactions")
    
    conn.commit()
    conn.close()

    return redirect(url_for('account_dashboard', username=session.get('username')))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)