from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///organ_donation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ------------------- MODELS -------------------
class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    blood_group = db.Column(db.String(10))
    organ = db.Column(db.String(50))
    city = db.Column(db.String(50))
    contact = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class Recipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    blood_group = db.Column(db.String(10))
    organ_needed = db.Column(db.String(50))
    city = db.Column(db.String(50))
    contact = db.Column(db.String(50))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

class ApprovalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipient.id'))
    donor_id = db.Column(db.Integer, db.ForeignKey('donor.id'))
    status = db.Column(db.String(20), default='Pending')

with app.app_context():
    db.create_all()

# ------------------- ROUTES -------------------

@app.route('/')
def home():
    donors = Donor.query.all()
    recipients = Recipient.query.all()
    return render_template('home.html', donors=donors, recipients=recipients)

# ---------- DONOR ----------
@app.route('/donor-register', methods=['GET', 'POST'])
def donor_register():
    if request.method == 'POST':
        donor = Donor(
            name=request.form['name'],
            age=request.form['age'],
            blood_group=request.form['blood_group'],
            organ=request.form['organ'],
            city=request.form['city'],
            contact=request.form['contact'],
            email=request.form['email'],
            password=request.form['password']
        )
        db.session.add(donor)
        db.session.commit()
        return redirect(url_for('donor_login'))
    return render_template('donor_register.html')

@app.route('/donor-login', methods=['GET', 'POST'])
def donor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        donor = Donor.query.filter_by(email=email, password=password).first()
        if donor:
            session['donor_id'] = donor.id
            return redirect(url_for('donor_dashboard'))
        else:
            return render_template('donor_login.html', error="Invalid email or password")
    return render_template('donor_login.html')

@app.route('/donor-dashboard')
def donor_dashboard():
    if 'donor_id' not in session:
        return redirect(url_for('donor_login'))
    donor = Donor.query.get(session['donor_id'])
    return render_template('donor_dashboard.html', donor=donor)

@app.route('/delete-donor/<int:id>')
def delete_donor(id):
    donor = Donor.query.get(id)
    if not donor:
        return "Donor not found", 404

    # If admin is logged in → allow delete
    if 'admin' in session:
        db.session.delete(donor)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    # If donor themself is logged in → allow delete
    elif 'donor_id' in session and session['donor_id'] == id:
        db.session.delete(donor)
        db.session.commit()
        session.pop('donor_id', None)
        return redirect(url_for('home'))

    # Otherwise unauthorized
    return "Unauthorized action", 403

# ---------- RECIPIENT ----------
@app.route('/recipient-register', methods=['GET', 'POST'])
def recipient_register():
    if request.method == 'POST':
        recipient = Recipient(
            name=request.form['name'],
            age=request.form['age'],
            blood_group=request.form['blood_group'],
            organ_needed=request.form['organ_needed'],
            city=request.form['city'],
            contact=request.form['contact'],
            email=request.form['email'],
            password=request.form['password']
        )
        db.session.add(recipient)
        db.session.commit()
        return redirect(url_for('recipient_login'))
    return render_template('recipient_register.html')

@app.route('/recipient-login', methods=['GET', 'POST'])
def recipient_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        recipient = Recipient.query.filter_by(email=email, password=password).first()
        if recipient:
            session['recipient_id'] = recipient.id
            return redirect(url_for('recipient_dashboard'))
        else:
            return render_template('recipient_login.html', error="Invalid email or password")
    return render_template('recipient_login.html')

@app.route('/recipient_dashboard')
def recipient_dashboard():
    if 'recipient_id' not in session:
        return redirect(url_for('recipient_login'))

    recipient = Recipient.query.get(session['recipient_id'])

    # fetch donors and approval status
    donors = Donor.query.all()
    donor_data = []
    for d in donors:
        approval = ApprovalRequest.query.filter_by(donor_id=d.id, recipient_id=recipient.id).first()
        status = approval.status if approval else "Not Requested"
        donor_data.append({
            "id": d.id,
            "name": d.name,
            "blood_group": d.blood_group,
            "organ": d.organ,
            "city": d.city,
            "contact": d.contact if status == "Approved" else None,
            "status": status
        })

    return render_template('recipient_dashboard.html', recipient=recipient, matched_donors=donor_data)

@app.route('/delete-recipient/<int:id>')
def delete_recipient(id):
    recipient = Recipient.query.get(id)
    if not recipient:
        return "Recipient not found", 404

    # If admin is logged in → allow delete
    if 'admin' in session:
        db.session.delete(recipient)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))

    # If recipient themself is logged in → allow delete
    elif 'recipient_id' in session and session['recipient_id'] == id:
        db.session.delete(recipient)
        db.session.commit()
        session.pop('recipient_id', None)
        return redirect(url_for('home'))

    # Otherwise unauthorized
    return "Unauthorized action", 403

@app.route('/search_donor', methods=['GET', 'POST'])
def search_donor():
    if 'recipient_id' not in session:
        return redirect(url_for('recipient_login'))

    donors = []
    recipient = Recipient.query.get(session['recipient_id'])

    if request.method == 'POST':
        organ = request.form.get('search_organ', '').strip()
        blood = request.form.get('search_blood', '').strip()
        city = request.form.get('search_city', '').strip()

        query = Donor.query
        if organ:
            query = query.filter(Donor.organ.ilike(f"%{organ}%"))
        if blood:
            query = query.filter(Donor.blood_group.ilike(f"%{blood}%"))

        donors = query.all()

    # Attach approval status for each donor
    donor_data = []
    for d in donors:
        approval = ApprovalRequest.query.filter_by(donor_id=d.id, recipient_id=recipient.id).first()
        status = approval.status if approval else "Not Requested"
        donor_data.append({
            "id": d.id,
            "name": d.name,
            "blood_group": d.blood_group,
            "organ": d.organ,
            "city": d.city,
            "contact": d.contact if status == "Approved" else None,
            "status": status
        })

    return render_template('recipient_dashboard.html', recipient=recipient, matched_donors=donor_data)

@app.route('/ask_approval', methods=['POST'])
def ask_approval():
    if 'recipient_id' not in session:
        return "Unauthorized", 403
    donor_id = request.form.get('donor_id')
    recipient_id = session['recipient_id']

    # Check if already requested
    existing = ApprovalRequest.query.filter_by(recipient_id=recipient_id, donor_id=donor_id).first()
    if existing:
        return "Already requested"

    req = ApprovalRequest(recipient_id=recipient_id, donor_id=donor_id)
    db.session.add(req)
    db.session.commit()
    return "Approval request sent successfully!"

# ---------- ADMIN MODULE ----------
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid credentials")
    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    donors = Donor.query.all()
    recipients = Recipient.query.all()
    
    # Simple match logic
    matches = []
    for r in recipients:
        for d in donors:
            if r.organ_needed.lower() == d.organ.lower() and r.blood_group == d.blood_group:
                matches.append({"recipient": r, "donor": d})
    
    stats = {
        "total_donors": len(donors),
        "total_recipients": len(recipients),
        "total_matches": len(matches)
    }
    
    return render_template('admin_dashboard.html', donors=donors, recipients=recipients, matches=matches, stats=stats)

@app.route('/admin_requests')
def admin_requests():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    
    requests = ApprovalRequest.query.all()
    enriched = []
    for r in requests:
        donor = Donor.query.get(r.donor_id)
        recipient = Recipient.query.get(r.recipient_id)
        enriched.append({
            "id": r.id,
            "recipient": recipient.name if recipient else "Unknown",
            "donor": donor.name if donor else "Unknown",
            "organ": donor.organ if donor else "",
            "blood_group": donor.blood_group if donor else "",
            "status": r.status
        })
    return render_template('admin_requests.html', requests=enriched)

from flask import flash

@app.route('/approve_request/<int:id>', methods=['POST'])
def approve_request(id):
    if 'admin' not in session:
        return "Unauthorized", 403
    req = ApprovalRequest.query.get(id)
    if req:
        req.status = 'Approved'
        db.session.commit()
        flash("Recipient has been notified that the donor was approved!")
    return redirect(url_for('admin_requests'))

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ---------- RUN ----------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
