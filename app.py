from ast import Not
import os, json
from flask import Flask, make_response, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, fields, marshal_with, reqparse
from werkzeug.exceptions import HTTPException

# initialize flask app and set path to the database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///api_database.sqlite3'

# Initialize database
db = SQLAlchemy()
db.init_app(app)
app.app_context().push()

# Initialize API
api = Api(app)

# Models
class Student(db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    roll_number = db.Column(db.String, unique=True, nullable=False)
    first_name = db.Column(db.String, nullable=False)
    last_name = db.Column(db.String)
    courses = db.relationship('Course', secondary='enrollment')

class Course(db.Model):
    __tablename__ = 'course'
    course_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    course_code = db.Column(db.String, unique=True, nullable=False)
    course_name = db.Column(db.String, nullable=False)
    course_description = db.Column(db.String)

class Enrollment(db.Model):
    __tablename__ = 'enrollment'
    enrollment_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.course_id'), nullable=False)

# Functions
def c_id(course_no):
    return int(course_no.split('_')[1])

# Output fields
course_output_fields = {
    'course_id': fields.Integer,
    'course_name': fields.String,
    'course_code': fields.String,
    'course_description': fields.String
}
student_output_fields = {
    'student_id': fields.Integer,
    'first_name': fields.String,
    'last_name': fields.String,
    'roll_number': fields.String
}
enrollment_output_fields = {
    'enrollment_id': fields.Integer,
    'student_id': fields.Integer,
    'course_id': fields.Integer,
}


# Request parsers
course_parser = reqparse.RequestParser()
course_parser.add_argument('course_name')
course_parser.add_argument('course_code')
course_parser.add_argument('course_description')

student_parser = reqparse.RequestParser()
student_parser.add_argument('first_name')
student_parser.add_argument('last_name')
student_parser.add_argument('roll_number')

enrollment_parser = reqparse.RequestParser()
enrollment_parser.add_argument('course_id')

# Validations
class NotFoundError(HTTPException):
    def __init__(self, entity, status_code):
        self.response = make_response(f'{entity} not found', status_code)

class NotFoundError_custom_message(HTTPException):
    def __init__(self, message, status_code):
        self.response = make_response(message, status_code)

class InternalServerError(HTTPException):
    def __init__(self, status_code):
        self.response = make_response('Internal Server Error', status_code)

class BusinessValidationError(HTTPException):
    def __init__(self, status_code, error_code, error_message):
        message = {"error_code": error_code,
                   "error_message": error_message}
        self.response = make_response(message, status_code)

class AlreadyExistsError(HTTPException):
    def __init__(self, entity, status_code):
        self.response = make_response(f'{entity} already exists', status_code)

class AlreadyExistsError_custom_message(HTTPException):
    def __init__(self, message, status_code):
        self.response = make_response(message, status_code)

class EnrollmentConflictError(HTTPException):
    def __init__(self, status_code):
        self.response = make_response(f'Cannot delete. Students are already enrolled for this course. Please delete enrollments first.', status_code)

# API classes
class CourseAPI(Resource):
    @marshal_with(course_output_fields)
    def get(self, course_id):

        # 200, 404, 500
        try:
            course = Course.query.filter_by(course_id=course_id).first()
        except:
            raise InternalServerError(status_code=500)
        else:
            if course:
                return (course, 200)
            else:
                raise NotFoundError(entity='Course', status_code=404)
    
    @marshal_with(course_output_fields)
    def put(self, course_id):
        args = course_parser.parse_args()
        cname = args.get('course_name')
        ccode = args.get('course_code')
        cdesc = args.get('course_description')

        # 400 Bad Request
        if cname is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE001',
                                           error_message='Course Name is required and should be string.')
        if ccode is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE002',
                                           error_message='Course Code is required and should be string.')
        if cdesc is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE003',
                                           error_message='Course Description should be string.')
        
        # 404 Not Found
        course = Course.query.get(course_id)
        if course is None:
            raise NotFoundError(entity='Course', status_code=404)

        # 409
        dup_check = Course.query.filter_by(course_code=ccode).first()
        if dup_check and dup_check.course_id != course_id:
            raise AlreadyExistsError(entity='course_code', status_code=409)

        # 500 Internal Server Error, 200 Successfully updated
        try:
            course.course_name=cname
            course.course_code=ccode
            course.course_description=cdesc
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            return (course, 200)
    
    def delete(self, course_id):
        # 200, 404, 409, 500
        try:
            course = Course.query.filter_by(course_id=course_id).first()
        except:
            raise InternalServerError(status_code=500)
        else:
            if Enrollment.query.filter_by(course_id=course_id).first():
                raise EnrollmentConflictError(status_code=409)
            if course:
                db.session.delete(course)
                db.session.commit()
                return ("Successfully deleted", 200)
            else:
                raise NotFoundError(entity='Course', status_code=404)
    
    @marshal_with(course_output_fields)
    def post(self):
        args = course_parser.parse_args()
        cname = args.get('course_name')
        ccode = args.get('course_code')
        cdesc = args.get('course_description')
        
        # 400
        if cname is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE001',
                                           error_message='Course Name is required and should be string.')
        if ccode is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE002',
                                           error_message='Course Code is required and should be string.')
        if cdesc is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='COURSE003',
                                           error_message='Course Description should be string.')
        
        # 409
        if Course.query.filter_by(course_code=ccode).first():
            raise AlreadyExistsError(entity='course_code', status_code=409)
        
        # 500, 201
        try:
            new_course = Course(course_name=cname,
                                course_code=ccode,
                                course_description=cdesc)
            db.session.add(new_course)
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            return new_course, 201

class StudentAPI(Resource):
    @marshal_with(student_output_fields)
    def get(self, student_id):
        # 200, 404, 500
        try:
            student = Student.query.filter_by(student_id=student_id).first()
        except:
            raise InternalServerError(status_code=500)
        else:
            if student:
                return (student, 200)
            else:
                raise NotFoundError(entity='Student', status_code=404)
    
    @marshal_with(student_output_fields)
    def put(self, student_id):
        args = student_parser.parse_args()
        fname = args.get('first_name')
        lname = args.get('last_name')
        roll = args.get('roll_number')
        
        # 400 Bad Request
        if roll is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='STUDENT001',
                                           error_message='Roll Number required and should be String.')
        if fname is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='STUDENT002',
                                           error_message='First Name is required and should be string.')
        
        # 404 Not Found
        student = Student.query.get(student_id)
        if student is None:
            raise NotFoundError(entity='Student', status_code=404)

        # 409
        dup_check = Student.query.filter_by(roll_number=roll).first()
        if dup_check and dup_check.student_id != student_id:
            raise AlreadyExistsError(entity='roll_number', status_code=409)

        # 500 Internal Server Error, 200 Successfully updated
        try:
            student.first_name=fname
            student.last_name=lname
            student.roll_number=roll
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            return (student, 200)
    
    def delete(self, student_id):
        # 200, 404, 500
        try:
            student = Student.query.filter_by(student_id=student_id).first()
        except:
            raise InternalServerError(status_code=500)
        else:
            if student:
                db.session.delete(student)
                db.session.commit()
                return ("Successfully deleted", 200)
            else:
                raise NotFoundError(entity='Student', status_code=404)
    
    @marshal_with(student_output_fields)
    def post(self):
        args = student_parser.parse_args()
        fname = args.get('first_name')
        lname = args.get('last_name')
        roll = args.get('roll_number')
        
        # 400 Bad Request
        if roll is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='STUDENT001',
                                           error_message='Roll Number required and should be String.')
        if fname is None:
            raise BusinessValidationError( status_code=400,
                                           error_code='STUDENT002',
                                           error_message='First Name is required and should be string.')

        # 409
        if Student.query.filter_by(roll_number=roll).first():
            raise AlreadyExistsError(entity='roll_number', status_code=409)

        # 500, 201
        try:
            new_student = Student(  first_name=fname,
                                    last_name=lname,
                                    roll_number=roll)
            db.session.add(new_student)
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            return new_student, 201
        
class EnrollmentAPI(Resource):
    @marshal_with(enrollment_output_fields)
    def get(self, student_id):
        if Student.query.get(student_id) is None:
            raise BusinessValidationError(status_code=400, error_code='ENROLLMENT002', error_message='Student does not exist.')
        enrollments = Enrollment.query.filter_by(student_id=student_id).all()
        if enrollments == []:
            raise NotFoundError_custom_message(message='Student is not enrolled in any course', status_code=404)
        return enrollments, 200
    
    @marshal_with(enrollment_output_fields)
    def post(self, student_id):
        args = enrollment_parser.parse_args()
        cid = args.get('course_id')

        # 400 Bad Request
        if cid is None:
            raise BusinessValidationError(status_code=400, error_code='', error_message='course_id is required and must be an integer.')

        # 404 Not Found
        if Student.query.get(student_id) is None:
            raise BusinessValidationError(status_code=404, error_code='ENROLLMENT002', error_message='Student does not exist.')
        
        if Course.query.get(cid) is None:
            raise BusinessValidationError(status_code=404, error_code='ENROLLMENT001', error_message='Course does not exist.')
        
        # 409 Already Enrolled
        if Enrollment.query.filter_by(student_id=student_id, course_id=cid).first():
            raise AlreadyExistsError_custom_message('Student is already enrolled to given course', status_code=409)

        # 201 Successfully enrolled
        try:
            new_enrollment = Enrollment(student_id=student_id, course_id=cid)
            db.session.add(new_enrollment)
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            enrollments = Enrollment.query.filter_by(student_id=student_id).all()
            return enrollments, 201

    def delete(self, student_id, course_id):
        # 400 Bad Request
        if Student.query.get(student_id) is None:
            raise BusinessValidationError(  status_code=400,
                                            error_code='ENROLLMENT002',
                                            error_message='Student does not exist.')
        
        if Course.query.get(course_id) is None:
            raise BusinessValidationError(  status_code=400,
                                            error_code='ENROLLMENT001',
                                            error_message='Course does not exist.')
        
        # 404 Not Found
        enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
        if enrollment is None:
            raise NotFoundError_custom_message('Enrollment for the student not found', status_code=404)
        
        # 500, 200
        try:
            db.session.delete(enrollment)
        except:
            db.session.rollback()
            raise InternalServerError(status_code=500)
        else:
            db.session.commit()
            return ('Successfully delete', 200)

# RESTful controllers
api.add_resource(CourseAPI, '/api/course', '/api/course/<int:course_id>')
api.add_resource(StudentAPI,'/api/student', '/api/student/<int:student_id>')
api.add_resource(EnrollmentAPI, '/api/student/<int:student_id>/course', '/api/student/<int:student_id>/course/<int:course_id>')

# Controllers
@app.route('/', methods=['GET', 'POST'])
def homepage():
    students = Student.query.all()
    return render_template('index.html', students=students)

@app.route('/student/create', methods=['GET', 'POST'])
def add_student():
    if request.method == 'GET':
        return render_template('add.html')
    
    if request.method == 'POST':
        try:
            roll = request.form.get('roll')

            # Checking if roll number already present
            if Student.query.filter_by(roll_number=roll).first():
                return render_template('exists.html')
            
            # Getting details if roll number is new
            f_name = request.form.get('f_name')
            l_name = request.form.get('l_name')
            courses = request.form.getlist('courses')
            
            # Adding Student & Enrollments
            new_student = Student(roll_number=roll, first_name=f_name, last_name=l_name)
            for course in courses:
                course = Course.query.get(c_id(course))
                new_student.courses.append(course)
            db.session.add(new_student)
        except:
            db.session.rollback()
            message = 'There was an error adding the student record.'
            return render_template('error.html', message=message)
        else:
            db.session.commit()
            return redirect(url_for('homepage'))

@app.route('/student/<int:student_id>/update', methods=['GET', 'POST'])
def update_student(student_id):
    if request.method == 'GET':
        try:
            student = Student.query.get(student_id)
        except:
            message = 'There was an error finding the student record.'
            return render_template('error.html', message=message)
        else:
            return render_template('update.html', student=student)
    
    if request.method == 'POST':
        try:
            # Get form data
            f_name = request.form.get('f_name')
            l_name = request.form.get('l_name')
            courses = request.form.getlist('courses')
            
            updated_courses = []
            for course in courses:
                course = Course.query.get(c_id(course))
                updated_courses.append(course)
            
            student = Student.query.get(student_id)
            student.first_name = f_name
            student.last_name = l_name
            student.courses = updated_courses
        except:
            db.session.rollback()
            message = 'There was an error updating the student record.'
            return render_template('error.html', message=message)
        else:
            db.session.commit()
            return redirect(url_for('homepage'))

@app.route('/student/<int:student_id>/delete')
def delete_student(student_id):
    try:
        student = Student.query.get(student_id)
        db.session.delete(student)
    except:
        db.session.rollback()
        message = 'There was an error deleting the student record.'
        return render_template('error.html', message=message)
    else:
        db.session.commit()
        return redirect(url_for('homepage'))

@app.route('/student/<int:student_id>')
def studentpage(student_id):
    try:
        student = Student.query.get(student_id)
    except:
        message = 'There was an error finding the student.'
        return render_template('error.html', message=message)
    else:
        return render_template('personal.html', student=student)

if __name__ == '__main__':
    app.run()


