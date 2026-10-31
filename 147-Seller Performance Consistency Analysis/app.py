from flask import Flask,render_template,request,redirect,session,flash
import sqlite3
import pandas as pd
import numpy as np

from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from flask import Response

app=Flask(__name__)
app.secret_key="secret"


def get_db():
    conn=sqlite3.connect("database.db")
    conn.row_factory=sqlite3.Row
    return conn


def init_db():

    conn=get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT)
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS sellers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller TEXT,
    month TEXT,
    orders INTEGER,
    ontime INTEGER,
    rating REAL,
    returns INTEGER,
    cancel INTEGER)
    """)

    conn.commit()

init_db()

# LOGIN

@app.route("/",methods=["GET","POST"])
def login():

    if request.method=="POST":

        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()

        user=conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (u,p)).fetchone()

        if user:
            session["user"]=u
            return redirect("/dashboard")

    return render_template("login.html")


# REGISTER

@app.route("/register",methods=["GET","POST"])
def register():

    if request.method=="POST":

        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()

        try:
            conn.execute(
            "INSERT INTO users(username,password) VALUES (?,?)",
            (u,p))
            conn.commit()

        except:
            flash("Username already exists","danger")

        return redirect("/")

    return render_template("register.html")


# DASHBOARD

@app.route("/dashboard")
def dashboard():

    conn = get_db()

    df = pd.read_sql_query("SELECT * FROM sellers", conn)

    if len(df) == 0:
        return render_template("dashboard.html",
        sellers=0,rating=0,orders=0,suspicious=0,data=[])

    df["risk_score"] = df.apply(risk_score, axis=1)

    # suspicious condition
    suspicious_df = df[df["risk_score"] >= 60]

    sellers = df["seller"].nunique()
    rating = round(df["rating"].mean(),2)
    orders = df["orders"].sum()

    suspicious = len(suspicious_df)

    data = df.to_dict(orient="records")

    return render_template(
        "dashboard.html",
        sellers=sellers,
        rating=rating,
        orders=orders,
        suspicious=suspicious,
        data=data
    )


# MANUAL DATA ENTRY

@app.route("/add",methods=["GET","POST"])
def add():

    if request.method=="POST":

        data=(
        request.form["seller"],
        request.form["month"],
        request.form["orders"],
        request.form["ontime"],
        request.form["rating"],
        request.form["returns"],
        request.form["cancel"]
        )

        conn=get_db()

        conn.execute("""
        INSERT INTO sellers
        (seller,month,orders,ontime,rating,returns,cancel)
        VALUES (?,?,?,?,?,?,?)
        """,data)

        conn.commit()

        flash("Seller data added successfully","success")

        return redirect("/dashboard")

    return render_template("add_data.html")


# SAMPLE DATA

@app.route("/generate")
def generate():

    conn = get_db()

    conn.execute("DELETE FROM sellers")

    sellers = ["AmazonHub","QuickCart","MegaStore","FlipDeals","FastShip"]

    for s in sellers:

        orders = np.random.randint(80,200)
        ontime = np.random.randint(50,orders)
        rating = round(np.random.uniform(2.5,5),2)
        returns = np.random.randint(0,20)
        cancel = np.random.randint(0,10)

        conn.execute("""
        INSERT INTO sellers
        (seller,month,orders,ontime,rating,returns,cancel)
        VALUES (?,?,?,?,?,?,?)
        """,(s,"March",orders,ontime,rating,returns,cancel))

    conn.commit()

    flash("Sample data generated","success")

    return redirect("/dashboard")

# To clear the data

@app.route("/clear")
def clear():

    conn = get_db()

    conn.execute("DELETE FROM sellers")

    conn.commit()

    flash("All seller data cleared successfully","warning")

    return redirect("/dashboard")

# To Download

@app.route("/download")
def download():

    conn = get_db()

    df = pd.read_sql_query("SELECT * FROM sellers", conn)

    csv = df.to_csv(index=False)

    return Response(
        csv,
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=seller_report.csv"}
    )


# RISK SCORE

def risk_score(row):

    return_rate=row["returns"]/row["orders"]
    cancel_rate=row["cancel"]/row["orders"]
    ontime_rate=row["ontime"]/row["orders"]

    risk=(0.4*(1-row["rating"]/5)+
          0.3*return_rate+
          0.2*cancel_rate+
          0.1*(1-ontime_rate))

    return round(risk*100,2)


# ANALYTICS

@app.route("/analytics")
def analytics():

    conn = get_db()

    df = pd.read_sql_query("SELECT * FROM sellers", conn)

    if len(df) == 0:
        flash("No data available","warning")
        return redirect("/dashboard")

    df["risk_score"] = df.apply(risk_score, axis=1)

    # AI anomaly detection
    model = IsolationForest(contamination=0.2)

    df["anomaly"] = model.fit_predict(
        df[["orders","ontime","rating","returns","cancel"]]
    )

    # KMeans clustering
    kmeans = KMeans(n_clusters=3)

    df["cluster"] = kmeans.fit_predict(
        df[["rating","returns","cancel"]]
    )

    sellers = list(df["seller"])
    scores = list(df["risk_score"])
    ratings = list(df["rating"])
    months = list(df["month"])

    suspicious = df[df["anomaly"] == -1]

    return render_template(
        "analytics.html",
        sellers=sellers,
        scores=scores,
        ratings=ratings,
        months=months,
        suspicious=suspicious.to_dict(orient="records")
    )


# DATASET UPLOAD

@app.route("/upload",methods=["GET","POST"])
def upload():

    if request.method=="POST":

        file=request.files["file"]

        if file.filename=="":
            flash("Please upload a file","warning")
            return redirect("/upload")

        if file.filename.endswith(".xlsx"):
            df=pd.read_excel(file,engine="openpyxl")

        elif file.filename.endswith(".csv"):
            df=pd.read_csv(file)

        else:
            flash("Unsupported format (.xlsx or .csv only)","danger")
            return redirect("/upload")

        conn=get_db()

        for _,row in df.iterrows():

            conn.execute("""
            INSERT INTO sellers
            (seller,month,orders,ontime,rating,returns,cancel)
            VALUES (?,?,?,?,?,?,?)
            """,
            (row["seller"],row["month"],row["orders"],
             row["ontime"],row["rating"],
             row["returns"],row["cancel"]))

        conn.commit()

        flash("Dataset uploaded successfully","success")

        return redirect("/dashboard")

    return render_template("upload.html")


# LOGOUT

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


if __name__=="__main__":
    app.run(debug=True)