# ============================================================
# SMARTGROW INVESTMENT
# WEBSITE PROTOTYPE
# Python + Flask + SQLite
#
# IMPORTANT:
# This is a development prototype.
# It does not accept deposits or make payouts.
# Package amounts are examples, not guaranteed returns.
# ============================================================

from flask import (
    Flask,
    request,
    redirect,
    url_for,
    session,
    render_template_string,
    flash
)

import sqlite3
import secrets
import os

from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SMARTGROW_SECRET_KEY",
    secrets.token_hex(32)
)

DATABASE = "smartgrow.db"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            referral_code TEXT NOT NULL UNIQUE,
            referred_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referred_by) REFERENCES users(id)
        )
    """)
        # Add phone column to existing databases if missing
    user_columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    if not any(column["name"] == "phone" for column in user_columns):
        connection.execute(
            "ALTER TABLE users ADD COLUMN phone TEXT"
        )

    connection.commit()
    # ========================================================
    # REFERRAL REWARDS
    # ========================================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS referral_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_user_id INTEGER NOT NULL UNIQUE,
            amount REAL NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'credited',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users(id),
            FOREIGN KEY (referred_user_id) REFERENCES users(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS referral_withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
        # ========================================================
    # WITHDRAWAL REQUESTS
    # ========================================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            admin_note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
        # ========================================================
    # SMARTGROW WALLET
    # ========================================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            reference TEXT UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ========================================================
    # DEPOSIT REQUESTS
    # ========================================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            payment_method TEXT NOT NULL DEFAULT 'Manual',
            payment_reference TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            admin_note TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ========================================================
    # PACKAGE PURCHASES
    # ========================================================

    connection.execute("""
        CREATE TABLE IF NOT EXISTS package_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            package_amount REAL NOT NULL,
            duration_days INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


initialize_database()


# ============================================================
# WEBSITE DESIGN
# ============================================================

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>{{ title }} - SmartGrow Investment</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f3f6fa;
            color: #1d2939;
        }

        header {
            background: #073b2a;
            color: white;
            padding: 20px;
        }

        nav {
            max-width: 1100px;
            margin: auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }

        nav h2 {
            margin: 0;
        }

        nav a {
            color: white;
            text-decoration: none;
            margin: 5px 8px;
        }

        .hero {
            background: #0b6b45;
            color: white;
            padding: 65px 20px;
            text-align: center;
        }

        .hero h1 {
            font-size: 38px;
            margin-bottom: 15px;
        }

        .hero p {
            font-size: 17px;
            line-height: 1.7;
        }

        .container {
            max-width: 1100px;
            margin: 35px auto;
            padding: 0 18px;
        }

        .card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 3px 12px #0000000d;
            margin-bottom: 20px;
        }

        .grid {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
        }

        .package {
            border-top: 4px solid #0b8a57;
        }

        .amount {
            font-size: 27px;
            color: #087443;
            font-weight: bold;
        }

        input {
            width: 100%;
            padding: 13px;
            margin: 8px 0 16px;
            border: 1px solid #ccd5df;
            border-radius: 7px;
            font-size: 16px;
        }

        button, .button {
            display: inline-block;
            background: #087443;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 7px;
            cursor: pointer;
            text-decoration: none;
            font-size: 15px;
        }

        button:hover, .button:hover {
            background: #075c36;
        }

        .secondary {
            background: #344054;
        }

        .notice {
            background: #fff4d6;
            border-left: 5px solid #e5a000;
            padding: 15px;
            line-height: 1.6;
            border-radius: 5px;
        }

        .success {
            background: #d9fbe5;
            padding: 12px;
            border-radius: 7px;
            margin-bottom: 15px;
        }

        .error {
            background: #ffe1e1;
            padding: 12px;
            border-radius: 7px;
            margin-bottom: 15px;
        }

        .form-box {
            max-width: 450px;
            margin: 35px auto;
        }

        footer {
            background: #073b2a;
            color: white;
            text-align: center;
            padding: 25px;
            margin-top: 50px;
        }

        .muted {
            color: #667085;
        }

        @media (max-width: 600px) {
            .hero h1 {
                font-size: 29px;
            }

            nav {
                align-items: flex-start;
            }
        }
    </style>
</head>

<body>

<header>
    <nav>
        <h2>SmartGrow</h2>

        <div>
            <a href="{{ url_for('home') }}">Home</a>
            <a href="{{ url_for('packages') }}">Packages</a>

            {% if session.get('user_id') %}
                <a href="{{ url_for('dashboard') }}">Dashboard</a>
                <a href="{{ url_for('logout') }}">Logout</a>
            {% else %}
                <a href="{{ url_for('register') }}">Register</a>
                <a href="{{ url_for('login') }}">Login</a>
            {% endif %}
        </div>
    </nav>
</header>

{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        <div class="container">
            {% for category, message in messages %}
                <div class="{{ category }}">{{ message }}</div>
            {% endfor %}
        </div>
    {% endif %}
{% endwith %}

{{ content | safe }}

<footer>
    <p>SmartGrow Investment</p>
    <p>Website prototype for development and testing.</p>
    <p>No deposits or payouts are enabled.</p>
</footer>

</body>
</html>
"""


# ============================================================
# HELPER: DISPLAY A PAGE
# ============================================================

def show_page(title, content, **context):
    rendered_content = render_template_string(
        content,
        **context
    )

    return render_template_string(
        PAGE,
        title=title,
        content=rendered_content
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    content = """
    <section class="hero">
        <h1>Welcome to SmartGrow</h1>

        <p>
            Explore our proposed package options,
            create an account and view your member dashboard.
        </p>

        <br>

        <a class="button" href="{{ url_for('register') }}">
            Create Account
        </a>

        <a class="button secondary"
           href="{{ url_for('packages') }}">
            View Packages
        </a>
    </section>

    <div class="container">

        <div class="notice">
            <strong>Development notice:</strong>
            SmartGrow is currently a prototype.
            No real investments, deposits, withdrawals
            or referral payments are processed.
            Investment returns are not guaranteed.
        </div>

        <div class="grid" style="margin-top: 25px;">

            <div class="card">
                <h3>Member Accounts</h3>
                <p>
                    Create an account and securely sign in
                    to access your member dashboard.
                </p>
            </div>

            <div class="card">
                <h3>Package Options</h3>
                <p>
                    Browse the proposed package amounts
                    while the website is being developed.
                </p>
            </div>

            <div class="card">
                <h3>Referral Tracking</h3>
                <p>
                    View your personal referral code
                    and track accounts registered through it.
                </p>
            </div>

        </div>
    </div>
    """

    return show_page("Home", content)


# ============================================================
# PACKAGES
# ============================================================

@app.route("/packages")
def packages():

    package_options = [
        {
            "amount": 400,
            "profit": 150,
            "total": 550,
            "duration": 3
        },
        {
            "amount": 600,
            "profit": 225,
            "total": 825,
            "duration": 3
        },
        {
            "amount": 1000,
            "profit": 450,
            "total": 1450,
            "duration": 3
        },
        {
            "amount": 5000,
            "profit": 2500,
            "total": 7500,
            "duration": 7
        },
        {
            "amount": 10000,
            "profit": 7000,
            "total": 17000,
            "duration": 7
        },
        {
            "amount": 20000,
            "profit": 14000,
            "total": 34000,
            "duration": 7
        },
        {
            "amount": 30000,
            "profit": 17000,
            "total": 47000,
            "duration": 14
        },
        {
            "amount": 50000,
            "profit": 22000,
            "total": 72000,
            "duration": 14
        },
        {
            "amount": 70000,
            "profit": 28000,
            "total": 98000,
            "duration": 14
        }
    ]

    content = """
    <div class="container">

        <h1 style="text-align:center;">
            SmartGrow Investment Packages
        </h1>

        <p style="text-align:center;">
            Choose the package that suits you.
        </p>

        <div class="grid" style="margin-top:30px;">

            {% for package in package_options %}

                <div class="card package">

                    <h3>
                        Package {{ loop.index }}
                    </h3>

                    <div class="amount">
                        KES {{ "{:,}".format(package.amount) }}
                    </div>

                    <hr>

                    <p>
                        <strong>Investment Amount</strong><br>
                        KES {{ "{:,}".format(package.amount) }}
                    </p>

                    <p>
                        <strong>Return</strong><br>
                        <span style="color:#0b6b45; font-size:22px;">
                            KES {{ "{:,}".format(package.profit) }}
                        </span>
                    </p>

                    <p>
                        <strong>Total Payout</strong><br>
                        <span style="font-size:24px; font-weight:bold;">
                            KES {{ "{:,}".format(package.total) }}
                        </span>
                    </p>

                    <p>
                        <strong>Duration</strong><br>
                        {{ package.duration }} days
                    </p>

                    {% if session.get('user_id') %}

                        <a class="button"
                           href="{{ url_for('dashboard') }}">
                            Member Dashboard
                        </a>

                    {% else %}

                        <a class="button"
                           href="{{ url_for('register') }}">
                            Create Account
                        </a>

                    {% endif %}

                </div>

            {% endfor %}

        </div>

    </div>
    """

    return show_page(
        "Investment Packages",
        content,
        package_options=package_options
    )


# ============================================================
# REGISTRATION
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        phone = request.form.get(
            "phone", ""
        ).strip().replace(" ", "").replace("-", "")

        referral_input = request.form.get(
            "referral_code", ""
        ).strip().upper()

        # Validate username
        if len(username) < 3:
            flash(
                "Username must contain at least 3 characters.",
                "error"
            )
            return redirect(url_for("register"))

        # Validate password
        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "error"
            )
            return redirect(url_for("register"))

        # Validate Kenyan phone number
        if phone.startswith("+254"):
            phone = "0" + phone[4:]
        elif phone.startswith("254"):
            phone = "0" + phone[3:]

        if (
            len(phone) != 10
            or not phone.isdigit()
            or not phone.startswith(("07", "01"))
        ):
            flash(
                "Enter a valid Kenyan M-Pesa number, for example 0712345678.",
                "error"
            )
            return redirect(url_for("register"))

        connection = get_db()

        existing_user = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            connection.close()

            flash(
                "That username already exists. Choose another.",
                "error"
            )

            return redirect(url_for("register"))

        # Validate referral code
        referrer_id = None

        if referral_input:

            referrer = connection.execute(
                """
                SELECT id
                FROM users
                WHERE referral_code = ?
                """,
                (referral_input,)
            ).fetchone()

            if not referrer:
                connection.close()

                flash(
                    "That referral code is not valid.",
                    "error"
                )

                return redirect(url_for("register"))

            referrer_id = referrer["id"]

        # Generate unique referral code
        referral_code = secrets.token_hex(4).upper()

        while connection.execute(
            "SELECT id FROM users WHERE referral_code = ?",
            (referral_code,)
        ).fetchone():

            referral_code = secrets.token_hex(4).upper()

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create account with M-Pesa phone number
        connection.execute(
            """
            INSERT INTO users
            (username, password, phone, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                hashed_password,
                phone,
                referral_code,
                referrer_id
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Your account has been created. You can now log in.",
            "success"
        )

        return redirect(url_for("login"))

    content = """
    <div class="container form-box">

        <div class="card">
            <h1>Create Account</h1>

            <form method="POST">

                <label>Username</label>

                <input
                    type="text"
                    name="username"
                    minlength="3"
                    maxlength="40"
                    required
                >

                <label>Password</label>

                <input
                    type="password"
                    name="password"
                    minlength="8"
                    required
                >

                <label>M-Pesa Phone Number</label>

                <input
                    type="tel"
                    name="phone"
                    placeholder="0712345678"
                    maxlength="13"
                    required
                >

                <small>
                    Enter the Kenyan M-Pesa number you want to receive withdrawals on.
                </small>

                <label>
                    Referral Code
                    <span class="muted">(optional)</span>
                </label>

                <input
                    type="text"
                    name="referral_code"
                    maxlength="20"
                    value="{{ request.args.get('ref', '') }}"
                >

                <button type="submit">
                    Register
                </button>

            </form>

            <p>
                Already registered?
                <a href="{{ url_for('login') }}">Login here</a>.
            </p>

        </div>

    </div>
    """

    return show_page("Register", content)


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        connection = get_db()

        user = connection.execute(
            """
            SELECT id, username, password
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("dashboard"))

        flash(
            "Incorrect username or password.",
            "error"
        )

        return redirect(url_for("login"))

    content = """
    <div class="container form-box">

        <div class="card">
            <h1>Member Login</h1>

            <form method="POST">

                <label>Username</label>

                <input
                    type="text"
                    name="username"
                    required
                >

                <label>Password</label>

                <input
                    type="password"
                    name="password"
                    required
                >

                <button type="submit">
                    Login
                </button>

            </form>

            <p>
                Don't have an account?
                <a href="{{ url_for('register') }}">
                    Register here
                </a>.
            </p>

        </div>

    </div>
    """

    return show_page("Login", content)


# ============================================================
# MEMBER DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    connection = get_db()

    user = connection.execute(
        """
        SELECT id, username, referral_code, created_at
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    if not user:
        connection.close()
        session.clear()

        flash("Please log in again.", "error")
        return redirect(url_for("login"))

    referrals = connection.execute(
        """
        SELECT username, created_at
        FROM users
        WHERE referred_by = ?
        ORDER BY id DESC
        """,
        (user["id"],)
    ).fetchall()

    connection.close()

    referral_link = url_for(
        "register",
        ref=user["referral_code"],
        _external=True
    )

    content = """
    <div class="container">

        <h1>Member Dashboard</h1>

        <div class="grid">

            <div class="card">
                <h3>Welcome</h3>
                <p>{{ user['username'] }}</p>
            </div>

            <div class="card">
                <h3>Account Status</h3>
                <p>Registered member</p>
            </div>

            <div class="card">
                <h3>Referral Registrations</h3>
                <p>{{ referrals|length }}</p>
            </div>

        </div>

        <div class="card">
            <h2>Your Referral Code</h2>

            <p class="amount">
                {{ user['referral_code'] }}
            </p>

            <p>Referral registration link:</p>

            <input
                type="text"
                value="{{ referral_link }}"
                readonly
                onclick="this.select()"
            >

            <p class="muted">
                Share this link to track registrations.
                No referral payments are enabled.
            </p>
        </div>

        <div class="card">
            <h2>Your Registered Referrals</h2>

            {% if referrals %}

                <ul>
                    {% for referral in referrals %}
                        <li>
                            {{ referral['username'] }}
                            — {{ referral['created_at'] }}
                        </li>
                    {% endfor %}
                </ul>

            {% else %}

                <p>
                    No accounts have registered using
                    your referral code yet.
                </p>

            {% endif %}
        </div>
    <div class="card">
        <h2>Investment Account</h2>

        <p>
            Manage your funds and view the available packages.
        </p>

        <a class="button"
           href="{{ url_for('wallet') }}">
            My Wallet
        </a>

        <a class="button"
           href="{{ url_for('packages') }}">
            View Packages
        </a>
    </div>

    </div>
    """

    return show_page(
        "Dashboard",
        content,
        user=user,
        referrals=referrals,
        referral_link=referral_link
    )
    # ============================================================
# SMARTGROW WALLET
# ============================================================

@app.route("/wallet")
def wallet():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_db()

    balance_result = connection.execute("""
        SELECT COALESCE(SUM(amount), 0) AS balance
        FROM wallet_transactions
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    balance = float(balance_result["balance"] or 0)

    transactions = connection.execute("""
        SELECT
            transaction_type,
            amount,
            description,
            created_at
        FROM wallet_transactions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
    """, (user_id,)).fetchall()

    deposit_requests = connection.execute("""
        SELECT
            amount,
            payment_method,
            payment_reference,
            status,
            requested_at
        FROM deposit_requests
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (user_id,)).fetchall()

    connection.close()

    content = """
    <div class="container">

        <h1>My SmartGrow Wallet</h1>

        <div class="card">
            <h2>Available Wallet Balance</h2>

            <div class="amount">
                KES {{ "{:,.2f}".format(balance) }}
            </div>

            <p class="muted">
                Only verified deposits approved by the administrator
                will be added to your available balance.
            </p>
        </div>

        <div class="card">

            <h2>Deposit Money</h2>

            <p>
                Submit a deposit request. Payments are not
                automatically verified at this stage.
            </p>

            <form method="POST"
                  action="{{ url_for('wallet_deposit') }}">

                <label>Deposit Amount (KES)</label>

                <input
                    type="number"
                    name="amount"
                    min="1"
                    step="1"
                    required
                >

                <br><br>

                <label>Payment Method</label>

                <select name="payment_method" required>
                    <option value="Manual">Manual / Pending M-Pesa Integration</option>
                </select>

                <br><br>

                <label>Payment Reference (if available)</label>

                <input
                    type="text"
                    name="payment_reference"
                    maxlength="100"
                    placeholder="Enter transaction code if available"
                >

                <br><br>

                <button type="submit">
                    Submit Deposit Request
                </button>

            </form>

            <p class="muted">
                Do not submit a payment reference unless it relates
                to a genuine payment. Submitting a request does not
                mean your wallet has been credited.
            </p>

        </div>

        <div class="card">

            <h2>Deposit Request History</h2>

            {% if deposit_requests %}

                <div style="overflow-x:auto;">

                    <table border="1"
                           cellpadding="10"
                           cellspacing="0"
                           width="100%">

                        <tr>
                            <th>Amount</th>
                            <th>Method</th>
                            <th>Reference</th>
                            <th>Status</th>
                            <th>Date</th>
                        </tr>

                        {% for deposit in deposit_requests %}

                            <tr>
                                <td>
                                    KES {{ "{:,.2f}".format(deposit["amount"]) }}
                                </td>

                                <td>
                                    {{ deposit["payment_method"] }}
                                </td>

                                <td>
                                    {{ deposit["payment_reference"] or "-" }}
                                </td>

                                <td>
                                    {{ deposit["status"] }}
                                </td>

                                <td>
                                    {{ deposit["requested_at"] }}
                                </td>
                            </tr>

                        {% endfor %}

                    </table>

                </div>

            {% else %}

                <p>You have not submitted any deposit requests.</p>

            {% endif %}

        </div>

        <div class="card">

            <h2>Wallet Transaction History</h2>

            {% if transactions %}

                <div style="overflow-x:auto;">

                    <table border="1"
                           cellpadding="10"
                           cellspacing="0"
                           width="100%">

                        <tr>
                            <th>Type</th>
                            <th>Amount</th>
                            <th>Description</th>
                            <th>Date</th>
                        </tr>

                        {% for transaction in transactions %}

                            <tr>
                                <td>
                                    {{ transaction["transaction_type"] }}
                                </td>

                                <td>
                                    KES {{ "{:,.2f}".format(transaction["amount"]) }}
                                </td>

                                <td>
                                    {{ transaction["description"] or "-" }}
                                </td>

                                <td>
                                    {{ transaction["created_at"] }}
                                </td>
                            </tr>

                        {% endfor %}

                    </table>

                </div>

            {% else %}

                <p>No wallet transactions yet.</p>

            {% endif %}

        </div>

        <a class="button"
           href="{{ url_for('dashboard') }}">
            Back to Dashboard
        </a>

        <a class="button secondary"
           href="{{ url_for('packages') }}">
            View Packages
        </a>

    </div>
    """

    return show_page(
        "My Wallet",
        content,
        balance=balance,
        transactions=transactions,
        deposit_requests=deposit_requests
    )


# ============================================================
# SUBMIT A WALLET DEPOSIT REQUEST
# ============================================================

@app.route("/wallet/deposit", methods=["POST"])
def wallet_deposit():

    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    amount_text = request.form.get("amount", "").strip()
    payment_method = request.form.get(
        "payment_method", "Manual"
    ).strip()

    payment_reference = request.form.get(
        "payment_reference", ""
    ).strip()

    if len(payment_reference) > 100:
        flash("The payment reference is too long.", "error")
        return redirect(url_for("wallet"))

    try:
        amount = float(amount_text)

        if amount <= 0 or not amount.is_integer():
            raise ValueError

    except (ValueError, TypeError):
        flash(
            "Enter a valid positive deposit amount in whole KES.",
            "error"
        )
        return redirect(url_for("wallet"))

    # Payments are not yet connected to M-Pesa.
    # Only create a pending request; do not credit the wallet here.

    connection = get_db()

    try:
        connection.execute("""
            INSERT INTO deposit_requests (
                user_id,
                amount,
                payment_method,
                payment_reference,
                status
            )
            VALUES (?, ?, ?, ?, 'Pending')
        """, (
            session["user_id"],
            amount,
            payment_method,
            payment_reference or None
        ))

        connection.commit()

        flash(
            "Deposit request submitted. Your wallet has not "
            "been credited. The payment must be verified first.",
            "success"
        )

    except sqlite3.Error:
        connection.rollback()

        flash(
            "Unable to submit your deposit request. Please try again.",
            "error"
        )

    finally:
        connection.close()

    return redirect(url_for("wallet"))
# ============================================================
# SMARTGROW ADMIN LOGIN
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin_username = os.environ.get(
            "SMARTGROW_ADMIN_USERNAME", "admin"
        )

        admin_password = os.environ.get(
            "SMARTGROW_ADMIN_PASSWORD", ""
        )

        if (
            admin_password
            and username == admin_username
            and secrets.compare_digest(password, admin_password)
        ):
            session["admin_logged_in"] = True

            flash("Admin login successful.", "success")

            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin username or password.", "error")

    content = """
    <div class="container">
        <div class="card">
            <h1>SmartGrow Admin Login</h1>

            <form method="POST">
                <label>Admin Username</label>
                <input
                    type="text"
                    name="username"
                    required
                >

                <br><br>

                <label>Admin Password</label>
                <input
                    type="password"
                    name="password"
                    required
                >

                <br><br>

                <button type="submit">Login as Admin</button>
            </form>
        </div>
    </div>
    """

    return show_page("Admin Login", content)


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def admin_dashboard():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    connection = get_db()
    members = connection.execute("""
        SELECT
            u.id,
            u.username,
            u.phone,
            u.referral_code,
            u.referred_by,
            u.created_at,
            (
                SELECT COUNT(*)
                FROM users AS referred
                WHERE referred.referred_by = u.id
            ) AS referral_count
        FROM users AS u
        ORDER BY u.id DESC
    """).fetchall()
    withdrawals = connection.execute("""
        SELECT
            withdrawals.id,
            withdrawals.user_id,
            withdrawals.amount,
            withdrawals.status,
            withdrawals.requested_at,
            withdrawals.reviewed_at,
            withdrawals.admin_note,
            users.username,
            users.phone
        FROM withdrawals
        JOIN users ON users.id = withdrawals.user_id
        ORDER BY withdrawals.id DESC
    """).fetchall()

    connection.close()

    content = """
    <div class="container">

        <h1>SmartGrow Admin Dashboard</h1>
                <div class="card">
            <h2>Registered Members</h2>

            <p>Total registered members: {{ members|length }}</p>

            {% if members %}
                <div style="overflow-x:auto;">
                    <table border="1"
                           cellpadding="10"
                           cellspacing="0"
                           width="100%">

                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>M-Pesa Number</th>
                            <th>Referral Code</th>
                            <th>Number of Referrals</th>
                            <th>Referred By (User ID)</th>
                            <th>Registration Date</th>
                        </tr>

                        {% for member in members %}
                            <tr>
                                <td>{{ member['id'] }}</td>
                                <td>{{ member['username'] }}</td>
                                <td>{{ member['phone'] or 'Not provided' }}</td>
                                <td>{{ member['referral_code'] }}</td>
                                <td>{{ member['referral_count'] }}</td>
                                <td>{{ member['referred_by'] or 'None' }}</td>
                                <td>{{ member['created_at'] }}</td>
                            </tr>
                        {% endfor %}

                    </table>
                </div>
            {% else %}
                <p>No members have registered yet.</p>
            {% endif %}
        </div>
        <div class="notice">
            Review every withdrawal request before making
            a decision. Approval does not send money.
        </div>

        <div class="card">
            <h2>Withdrawal Requests</h2>

            {% if withdrawals %}

                <div style="overflow-x:auto;">
                    <table border="1"
                           cellpadding="10"
                           cellspacing="0"
                           width="100%">

                        <tr>
                            <th>ID</th>
                            <th>Member</th>
                            <th>M-Pesa Number</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Requested</th>
                            <th>Admin Decision</th>
                        </tr>

                        {% for w in withdrawals %}

                            <tr>
                                <td>{{ w['id'] }}</td>
                                <td>{{ w['username'] }}</td>
                                <td>{{ w['phone'] or 'Not provided' }}</td>
                                <td>
                                KES {{ "{:,.2f}".format(w['amount']) }}
                                </td>
                                <td>{{ w['status'] }}</td>
                                <td>{{ w['requested_at'] }}</td>

                                <td>
                                    {% if w['status'] == 'Pending' %}

                                        <form method="POST"
                                              action="{{ url_for(
                                                  'review_withdrawal',
                                                  withdrawal_id=w['id']
                                              ) }}">

                                            <button
                                                type="submit"
                                                name="decision"
                                                value="Approved">
                                                Approve
                                            </button>

                                            <button
                                                type="submit"
                                                name="decision"
                                                value="Rejected">
                                                Reject
                                            </button>

                                            <br><br>

                                            <input
                                                type="text"
                                                name="admin_note"
                                                placeholder="Optional note"
                                            >

                                        </form>

                                    {% else %}

                                        {{ w['status'] }}

                                        {% if w['admin_note'] %}
                                            <br>
                                            {{ w['admin_note'] }}
                                        {% endif %}

                                    {% endif %}
                                </td>
                            </tr>

                        {% endfor %}

                    </table>
                </div>

            {% else %}

                <p>No withdrawal requests have been submitted.</p>

            {% endif %}
        </div>

        <a class="button secondary"
           href="{{ url_for('admin_logout') }}">
            Admin Logout
        </a>

    </div>
    """
    return show_page(
    "Admin Dashboard",
    content,
    withdrawals=withdrawals,
    members=members
)


# ============================================================
# APPROVE OR REJECT A WITHDRAWAL
# ============================================================

@app.route(
    "/admin/withdrawal/<int:withdrawal_id>/review",
    methods=["POST"]
)
def review_withdrawal(withdrawal_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    decision = request.form.get("decision", "")
    admin_note = request.form.get("admin_note", "").strip()

    if decision not in ["Approved", "Rejected"]:
        flash("Invalid decision.", "error")
        return redirect(url_for("admin_dashboard"))

    connection = get_db()

    withdrawal = connection.execute(
        """
        SELECT id, status
        FROM withdrawals
        WHERE id = ?
        """,
        (withdrawal_id,)
    ).fetchone()

    if not withdrawal:
        connection.close()
        flash("Withdrawal request not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if withdrawal["status"] != "Pending":
        connection.close()
        flash("This request has already been reviewed.", "error")
        return redirect(url_for("admin_dashboard"))

    connection.execute(
        """
        UPDATE withdrawals
        SET status = ?,
            reviewed_at = CURRENT_TIMESTAMP,
            admin_note = ?
        WHERE id = ?
          AND status = 'Pending'
        """,
        (decision, admin_note, withdrawal_id)
    )

    connection.commit()
    connection.close()

    flash(
        "Withdrawal request marked " + decision + ".",
        "success"
    )

    return redirect(url_for("admin_dashboard"))


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)

    flash("Admin logged out.", "success")

    return redirect(url_for("admin_login"))


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have logged out.", "success")

    return redirect(url_for("home"))


# ============================================================
# START WEBSITE
# ============================================================

if __name__ == "__main__":

    print("=" * 50)
    print("SMARTGROW INVESTMENT WEBSITE")
    print("=" * 50)
    print("Open your browser and visit:")
    print("http://127.0.0.1:5000")
    print("=" * 50)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )