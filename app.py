from flask import Flask, request, render_template, redirect, url_for, session
import MySQLdb
import MySQLdb.cursors 

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

# No password hashing. Completely insecure.
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

#Insecure Login Route
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_db_connection()
        c = conn.cursor()

        # Fully vulnerable SQL query
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        
        print(f"Executing SQL Query: {query}")  # Debugging
        
        c.execute(query)  # Direct execution without sanitization
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

    # Vulnerable Query allows SQL Injection
    query = f"SELECT username, balance FROM users WHERE username = '{username}'"
    print(f"Executing SQL Query: {query}")  # Debugging
    c.execute(query)
    user = c.fetchone()

    # SQL Injection Vulnerable Transaction Query
    if username == 'admin':
        c.execute(f"SELECT sender, recipient, amount, timestamp FROM transactions ORDER BY timestamp DESC")
    else:
        c.execute(f"SELECT sender, recipient, amount, timestamp FROM transactions WHERE sender = '{username}' OR recipient = '{username}' ORDER BY timestamp DESC")
    
    transactions = c.fetchall()

    users = []
    if username == 'admin':
        c.execute(f"SELECT username, balance FROM users")
        users = c.fetchall()

    conn.close()

    message = ""

    if request.method == 'POST':
        recipient = request.form.get('recipient')
        sender = request.form.get('sender') if username == 'admin' else username
        amount = request.form.get('amount')

        try:
            amount = float(amount)
            if amount <= 0:
                message = "Transaction amount must be positive!"
            elif recipient and sender:
                conn = get_db_connection()
                c = conn.cursor()

                # SQL Injection Vulnerable Balance Update
                c.execute(f"UPDATE users SET balance = balance - {amount} WHERE username = '{sender}'")
                c.execute(f"UPDATE users SET balance = balance + {amount} WHERE username = '{recipient}'")
                conn.commit()

                # SQL Injection Vulnerable Transaction Insertion
                c.execute(f"INSERT INTO transactions (sender, recipient, amount) VALUES ('{sender}', '{recipient}', {amount})")
                conn.commit()

                conn.close()
                return redirect(url_for('account_dashboard', username=username))
        except ValueError:
            message = "Invalid transaction amount!"

    return render_template('account.html', user=user, transactions=transactions, users=users, message=message)

# Insecure Account Creation
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    message = ""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_db_connection()
        c = conn.cursor()

        # Allows SQL injection to check for existing users
        c.execute(f"SELECT * FROM users WHERE username = '{username}'")
        existing_user = c.fetchone()

        if existing_user:
            message = "Username already taken!"
        else:
            # No input sanitization. SQL injection is possible.
            query = f"INSERT INTO users (username, password, balance) VALUES ('{username}', '{password}', 100.00)"
            print(f"Executing SQL Query: {query}")
            c.execute(query)
            conn.commit()
            message = "Account created successfully!"
        
        conn.close()
    
    return render_template('create_account.html', message=message)

@app.route('/reset_transactions', methods=['POST'])
def reset_transactions():
    # No session validation. Anyone can reset transactions.
    conn = get_db_connection()
    c = conn.cursor()

    # This will delete all transactions
    c.execute("DELETE FROM transactions")
    
    conn.commit()
    conn.close()

    return redirect(url_for('account_dashboard', username=session.get('username')))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)