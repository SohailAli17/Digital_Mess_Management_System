from flask import Flask, make_response, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, Meal, Payment
from config import Config
from datetime import datetime, date, timedelta
import csv
from io import StringIO

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def calculate_balance(user_id, start_date=None, end_date=None):
    if not start_date:
        start_date = datetime.strptime('2023-01-01', '%Y-%m-%d').date()  # Start from a very early date
    if not end_date:
        end_date = date.today()

    meals = Meal.query.filter_by(student_id=user_id) \
                      .filter(Meal.date >= start_date) \
                      .filter(Meal.date <= end_date) \
                      .all()
    
    payments = Payment.query.filter_by(student_id=user_id) \
                           .filter(Payment.date >= start_date) \
                           .filter(Payment.date <= end_date) \
                           .all()

    total_meals = sum(m.breakfast + m.lunch + m.dinner for m in meals)
    total_due = total_meals * app.config['MEAL_COST']
    total_paid = sum(p.amount for p in payments)
    balance = total_paid - total_due

    return total_due, total_paid, balance

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        roll_no = request.form['roll_no']
        room_no = request.form['room_no']
        contact = request.form['contact']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            name=name,
            roll_no=roll_no,
            room_no=room_no,
            contact=contact,
            role='student'
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Admin Routes

# app.py

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('login'))
    
    today = date.today()
    
    # Calculate today's meal counts
    today_meals = Meal.query.filter_by(date=today).all()
    breakfast_count = sum(1 for meal in today_meals if meal.breakfast)
    lunch_count = sum(1 for meal in today_meals if meal.lunch)
    dinner_count = sum(1 for meal in today_meals if meal.dinner)
    
    # Calculate total payments
    total_payments = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
    
    #Calculate total
    total_students = User.query.filter_by(role='student').count()
    
    # Calculate total dues for all students
    all_students = User.query.filter_by(role='student').all()
    total_dues = 0
    
    for student in all_students:
        meals_count = Meal.query.filter_by(student_id=student.id).count()
        payments_count = Payment.query.filter_by(student_id=student.id).count()

        total_meals_cost = meals_count * Config.MEAL_COST
        total_payments_received = db.session.query(db.func.sum(Payment.amount)).filter_by(student_id=student.id).scalar() or 0

        student_balance = total_meals_cost - total_payments_received

        # Dues are only for negative balance (money owed by the student)
        if student_balance > 0:
            total_dues += student_balance

    return render_template('admin/dashboard.html', 
                           breakfast_count=breakfast_count, 
                           lunch_count=lunch_count, 
                           dinner_count=dinner_count,
                           total_students=total_students,
                           total_payments=total_payments,
                           total_dues=total_dues)

# app.py

@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
def admin_students():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        # Check if the request is for deletion
        if 'delete' in request.form:
            student_id = request.form.get('student_id')
            student = User.query.get(student_id)
            if student:
                # Delete related meals and payments first to avoid integrity errors
                Meal.query.filter_by(student_id=student.id).delete()
                Payment.query.filter_by(student_id=student.id).delete()
                db.session.delete(student)
                db.session.commit()
                flash(f"Student {student.name} deleted successfully.", 'success')
            else:
                flash("Student not found.", 'danger')
        else: # This is an add or edit request
            student_id = request.form.get('student_id')
            username = request.form['username']
            name = request.form['name']
            roll_no = request.form['roll_no']
            room_no = request.form['room_no']
            contact = request.form['contact']
            password = request.form['password']

            if student_id:
                # This is an edit operation
                student = User.query.get(student_id)
                if student:
                    student.username = username
                    student.name = name
                    student.roll_no = roll_no
                    student.room_no = room_no
                    student.contact = contact
                    if password:
                        student.set_password(password)
                    db.session.commit()
                    flash('Student updated successfully!', 'success')
                else:
                    flash('Student not found!', 'danger')
            else:
                # This is a create operation
                new_student = User(username=username, name=name, roll_no=roll_no, room_no=room_no, contact=contact, role='student')
                new_student.set_password(password)
                db.session.add(new_student)
                db.session.commit()
                flash('Student added successfully!', 'success')

    students = User.query.filter_by(role='student').all()
    return render_template('admin/students.html', students=students)
@app.route('/admin/attendance', methods=['GET', 'POST'])
@login_required
def admin_attendance():
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    selected_date = request.args.get('date', date.today().isoformat())
    
    if request.method == 'POST':
        try:
            # Use get() method to avoid KeyError
            student_id = request.form.get('student_id')
            meal_type = request.form.get('meal_type')
            action = request.form.get('action')  # mark or unmark
            
            if not all([student_id, meal_type, action]):
                return jsonify({'success': False, 'error': 'Missing parameters'})
            
            # Convert string date to Python date object
            try:
                selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            except ValueError:
                selected_date_obj = date.today()
            
            # Get or create meal record for the student on the selected date
            meal = Meal.query.filter_by(student_id=student_id, date=selected_date_obj).first()
            if not meal:
                meal = Meal(student_id=student_id, date=selected_date_obj)
                db.session.add(meal)
            
            # Update the specific meal type
            if meal_type == 'breakfast':
                meal.breakfast = (action == 'mark')
            elif meal_type == 'lunch':
                meal.lunch = (action == 'mark')
            elif meal_type == 'dinner':
                meal.dinner = (action == 'mark')
            
            db.session.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)})
    
    # Convert selected_date string to date object for querying
    try:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date_obj = date.today()
    
    students = User.query.filter_by(role='student').all()
    meals = Meal.query.filter_by(date=selected_date_obj).all()
    
    # Create a dictionary for quick lookup
    meal_dict = {meal.student_id: meal for meal in meals}
    
    return render_template('admin/attendance.html', 
                         students=students, 
                         meal_dict=meal_dict,
                         selected_date=selected_date)

@app.route('/admin/payments', methods=['GET', 'POST'])
@login_required
def admin_payments():
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        student_id = request.form['student_id']
        amount = request.form['amount']
        
        payment = Payment(
            student_id=student_id,
            amount=amount,
            status='paid'
        )
        db.session.add(payment)
        db.session.commit()
        flash('Payment recorded successfully')
    
    students = User.query.filter_by(role='student').all()
    payments = Payment.query.all()
    return render_template('admin/payments.html', students=students, payments=payments)


@app.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('admin_dashboard'))

    report_type = request.args.get('type', 'attendance')
    start_date_str = request.args.get('start_date', (date.today() - timedelta(days=7)).strftime('%Y-%m-%d'))
    end_date_str = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    data = {
        'report_type': report_type,
        'start_date': start_date,
        'end_date': end_date,
    }

    if report_type == 'attendance':
        # Fetch meal records within the date range
        meals = Meal.query.filter(Meal.date.between(start_date, end_date)).order_by(Meal.date, Meal.student_id).all()
        report_data = []
        for meal in meals:
            report_data.append({
                'date': meal.date,
                'student_name': meal.student.name,
                'roll_no': meal.student.roll_no,
                'breakfast': meal.breakfast,
                'lunch': meal.lunch,
                'dinner': meal.dinner,
                'total': sum([meal.breakfast, meal.lunch, meal.dinner])
            })
        data['meals'] = report_data
    
    elif report_type == 'defaulters':
        defaulters_list = []
        all_students = User.query.filter_by(role='student').all()
        for student in all_students:
            meals_cost = db.session.query(db.func.sum(db.cast(Meal.breakfast, db.Integer) + 
                                                      db.cast(Meal.lunch, db.Integer) + 
                                                      db.cast(Meal.dinner, db.Integer)))\
                                  .filter_by(student_id=student.id).scalar() or 0
            
            total_payments = db.session.query(db.func.sum(Payment.amount)).filter_by(student_id=student.id).scalar() or 0
            
            # The balance is what the student paid minus what they owe
            balance = total_payments - (meals_cost * Config.MEAL_COST)

            if balance < 0:
                defaulters_list.append({
                    'student': student,
                    'total_paid': total_payments,
                    'total_due': meals_cost * Config.MEAL_COST,
                    'balance': balance
                })
        data['defaulters'] = defaulters_list
    
    elif report_type == 'collections':
        collections_data = []
        payments = Payment.query.filter(Payment.date.between(start_date, end_date)).all()
        monthly_collections = {}
        for payment in payments:
            month_year = payment.date.strftime('%Y-%m')
            monthly_collections.setdefault(month_year, 0)
            monthly_collections[month_year] += payment.amount

        for month, total in sorted(monthly_collections.items()):
            collections_data.append({
                'month': datetime.strptime(month, '%Y-%m').strftime('%B %Y'),
                'total': total
            })
        data['collections'] = collections_data

    elif report_type == 'payments':
        payments = Payment.query.filter(Payment.date.between(start_date, end_date))\
                                .order_by(Payment.date).all()
        report_data = []
        for payment in payments:
            report_data.append({
                'date': payment.date,
                'student_name': payment.student.name,
                'roll_no': payment.student.roll_no,
                'amount': payment.amount,
                'status': payment.status
            })
        data['payments'] = report_data

    return render_template('admin/reports.html', **data)


@app.route('/admin/reports/export')
@login_required
def export_reports():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('admin_dashboard'))

    report_type = request.args.get('type')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    si = StringIO()
    cw = csv.writer(si)

    filename = f"{report_type}_report_{start_date}_to_{end_date}.csv"
    
    if report_type == 'attendance':
        cw.writerow(['Date', 'Student Name', 'Roll No', 'Breakfast', 'Lunch', 'Dinner'])
        meals = Meal.query.filter(Meal.date.between(start_date, end_date)).order_by(Meal.date, Meal.student_id).all()
        for meal in meals:
            cw.writerow([
                meal.date.strftime('%Y-%m-%d'),
                meal.student.name,
                meal.student.roll_no,
                'Yes' if meal.breakfast else 'No',
                'Yes' if meal.lunch else 'No',
                'Yes' if meal.dinner else 'No'
            ])
            
    elif report_type == 'defaulters':
        cw.writerow(['Student Name', 'Roll No', 'Total Paid', 'Total Dues', 'Balance'])
        all_students = User.query.filter_by(role='student').all()
        for student in all_students:
            meals_cost = db.session.query(db.func.sum(db.cast(Meal.breakfast, db.Integer) + 
                                                      db.cast(Meal.lunch, db.Integer) + 
                                                      db.cast(Meal.dinner, db.Integer)))\
                                  .filter_by(student_id=student.id).scalar() or 0
            total_payments = db.session.query(db.func.sum(Payment.amount)).filter_by(student_id=student.id).scalar() or 0
            balance = total_payments - (meals_cost * Config.MEAL_COST)

            if balance < 0:
                cw.writerow([
                    student.name,
                    student.roll_no,
                    f"₹{total_payments:.2f}",
                    f"₹{meals_cost * Config.MEAL_COST:.2f}",
                    f"₹{balance:.2f}"
                ])

    elif report_type == 'collections':
        cw.writerow(['Month', 'Total Collection'])
        payments = Payment.query.filter(Payment.date.between(start_date, end_date)).all()
        monthly_collections = {}
        for payment in payments:
            month_year = payment.date.strftime('%Y-%m')
            monthly_collections.setdefault(month_year, 0)
            monthly_collections[month_year] += payment.amount

        for month, total in sorted(monthly_collections.items()):
            cw.writerow([
                datetime.strptime(month, '%Y-%m').strftime('%B %Y'),
                f"₹{total:.2f}"
            ])

    elif report_type == 'payments':
        cw.writerow(['Date', 'Student Name', 'Roll No', 'Amount', 'Status'])
        payments = Payment.query.filter(Payment.date.between(start_date, end_date))\
                                .order_by(Payment.date).all()
        for payment in payments:
            cw.writerow([
                payment.date.strftime('%Y-%m-%d'),
                payment.student.name,
                payment.student.roll_no,
                f"₹{payment.amount:.2f}",
                payment.status
            ])
            
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv"
    return output

# Student Routes
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('admin_dashboard'))

    # Get today's meal status
    today_meal = Meal.query.filter_by(student_id=current_user.id, date=date.today()).first()
    
    # Calculate financial balance for the student
    total_due, total_paid, balance = calculate_balance(current_user.id)

    # Get recent meals for the table
    recent_meals = Meal.query.filter_by(student_id=current_user.id).order_by(Meal.date.desc()).limit(10).all()

    return render_template('student/dashboard.html',
                           today_meal=today_meal,
                           total_due=total_due,
                           total_paid=total_paid,
                           balance=balance,
                           recent_meals=recent_meals)


@app.route('/student/attendance')
@login_required
def student_attendance():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    
    meals = Meal.query.filter_by(student_id=current_user.id).filter(Meal.date.between(start_date, end_date)).all()
    
    return render_template('student/attendance.html', meals=meals, start_date=start_date, end_date=end_date)

@app.route('/student/payments')
@login_required
def student_payments():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    payments = Payment.query.filter_by(student_id=current_user.id).all()
    
    return render_template('student/payments.html', payments=payments)

@app.route('/student/profile', methods=['GET', 'POST'])
@login_required
def student_profile():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.roll_no = request.form['roll_no']
        current_user.room_no = request.form['room_no']
        current_user.contact = request.form['contact']
        
        password = request.form['password']
        if password:
            current_user.set_password(password)
        
        db.session.commit()
        flash('Profile updated successfully')
    
    return render_template('student/profile.html')

# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
        
#         # Create admin user if not exists
#         if not User.query.filter_by(username='admin').first():
#             admin = User(username='admin', role='admin')
#             admin.set_password('admin')
#             db.session.add(admin)
#             db.session.commit()
    
#     app.run(debug=True)