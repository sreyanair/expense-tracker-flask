import os
import mysql.connector
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key")

def get_db():
    # 1. Get the URL you pasted into Render's environment variables
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        # 2. Parse the Railway URL: mysql://user:password@host:port/database
        url = urlparse(db_url)
        return mysql.connector.connect(
            host=url.hostname,
            user=url.username,
            password=url.password,
            database=url.path[1:], # Removes the leading slash from the database name
            port=url.port
        )
    else:
        # 3. Fallback to your local settings if DATABASE_URL isn't found
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="flaskdb"
       )

def init_db():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            amount DECIMAL(10, 2) NOT NULL,
            category VARCHAR(50),
            description TEXT,
            date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    db.commit()
    cursor.close()
    db.close()

init_db()

if __name__ == "__main__":
    # Ensure the app binds to Render's port
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    

@app.route('/')
def home():
    return redirect(url_for('analytics'))

@app.route('/signup', methods=['GET','POST'])
def signup():
  if request.method == 'POST':
    name=request.form['name']
    email=request.form['email']
    password=request.form['password']

    hashed_password=generate_password_hash(password)

    conn=get_db()
    cursor=conn.cursor()

    cursor.execute("insert into users (name,email,password_hash) VALUES(%s,%s,%s)",(name,email,hashed_password))
    conn.commit()
    conn.close()

    return redirect('/login')

  return render_template('signup.html') 

@app.route('/login', methods=['GET','POST'])
def login():
  print("Method:", request.method)
  if request.method =='POST':
    email=request.form['email']
    password=request.form['password']
    print("Email:", email)
    print("Password:", password)

    conn= get_db()
    cursor= conn.cursor(dictionary=True)

    cursor.execute("SELECT* FROM users WHERE email=%s",(email,))
    user=cursor.fetchone()
    print("User from DB:", user)
    conn.close()

    if user and check_password_hash(user['password_hash'],password):
      print("Login Success")
      session['user_id']=user['id']
      session['user_name']=user['name']
      return redirect('/dashboard')
    else:
      print("Login failed")
      return "Invalid credentials"
    
  return render_template('login.html')

@app.route('/dashboard')
def dashboard():
  if 'user_id' not in session:
    return redirect('/login')

  return render_template('dashboard.html', name=session['user_name'])

@app.route('/logout')
def logout():
  session.clear()
  return redirect('/login')

@app.route('/expenses')
def expenses():
    if 'user_id' not in session:
        return redirect('/login')

    page = int(request.args.get('page', 1))
    limit = 5
    offset = (page - 1) * limit

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM expenses
        WHERE user_id=%s
        LIMIT %s OFFSET %s
    """, (session['user_id'], limit, offset))

    expenses = cursor.fetchall()
    conn.close()

    return render_template("expenses.html", expenses=expenses, page=page)

@app.route('/add_expense', methods=['GET','POST'])
def add_expense():
  if 'user_id' not in session:
    return redirect('/login')

  if request.method=='POST':
    amount=request.form['amount']
    category=request.form['category']
    description=request.form['description']
    date=request.form['date']

    conn=get_db()
    cursor=conn.cursor()
     
    cursor.execute(""" INSERT INTO  expenses(user_id,amount,category,description,date)VALUES(%s,%s,%s,%s,%s)""", 
    (session['user_id'],amount,category,description,date))

    conn.commit()
    conn.close()
    return redirect('/expenses')
      
  return render_template("add_expense.html")

@app.route('/delete/<int:id>')
def delete_expense(id):
  if 'user_id' not in session:
    return redirect('/login')

  conn=get_db()
  cursor=conn.cursor()

  cursor.execute("DELETE FROM expenses WHERE id=%s AND user_id=%s", (id,session['user_id']))

  conn.commit()
  conn.close()

  return redirect('/expenses')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        description = request.form['description']
        date = request.form['date']

        cursor.execute("""
            UPDATE expenses
            SET amount=%s, category=%s, description=%s, date=%s
            WHERE id=%s AND user_id=%s
        """, (amount, category, description, date, id, session['user_id']))

        conn.commit()
        conn.close()

        return redirect('/expenses')

    cursor.execute(
        "SELECT * FROM expenses WHERE id=%s AND user_id=%s",
        (id, session['user_id'])
    )

    expense = cursor.fetchone()
    conn.close()

    return render_template("edit_expense.html", expense=expense) 

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Total expense
    cursor.execute("""
        SELECT SUM(amount) AS total
        FROM expenses
        WHERE user_id = %s
    """, (session['user_id'],))

    total = cursor.fetchone()['total']

    cursor.execute("""
    SELECT category, SUM(amount) AS total
    FROM expenses
    WHERE user_id = %s
    GROUP BY category
""", (session['user_id'],))

    category_data = cursor.fetchall()

    cursor.execute("""
    SELECT MONTHNAME(date) AS month,
           SUM(amount) AS total
    FROM expenses
    WHERE user_id = %s
    GROUP BY MONTHNAME(date)
""", (session['user_id'],))

    monthly_data = cursor.fetchall()


    

    category_labels = [c['category'] for c in category_data]
    category_totals = [float(c['total']) for c in category_data]

    months = [m['month'] for m in monthly_data]
    monthly_totals = [float(m['total']) for m in monthly_data]

    conn.close()

    return render_template(
      "analytics.html",
      total=total,
      category_data=category_data,
      monthly_data=monthly_data,
      category_labels=category_labels,
      category_totals=category_totals,
      months=months,
      monthly_totals=monthly_totals
      ) 

if __name__ == "__main__":
    app.run(debug=True)
    

    

 

 








      


