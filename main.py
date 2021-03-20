# TODO ------------------ TODO BLOCK ------------------

# TODO - Use NJSON as database for json files
# TODO - Verify contact support email before usage using confirmation links
# TODO - Check if HTTP requests match with configuration functions
# TODO - Create special account
# TODO - Set comment names to profile links

# ------------------ END BLOCK ------------------


# ------------------ IMPORTS BLOCK ------------------

from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify
from functools import wraps
from flask_msearch import Search
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy.orm import relationship
import pyperclip
from wtforms import StringField, SubmitField, PasswordField, SelectField
from wtforms.validators import DataRequired, URL, Email
from flask_ckeditor import CKEditor, CKEditorField
import datetime as dt
from flask_mail import Mail, Message
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import UnmappedInstanceError
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_gravatar import Gravatar
import os
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from html2text import html2text
from sqlalchemy.dialects.postgresql import JSON
import random
import string

# ------------------ END BLOCK ------------------


# ------------------ APPLICATION CONFIG BLOCK ------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", 's9TIRvlsjBr79quz')
ckeditor = CKEditor(app)
Bootstrap(app)
months = [(i, dt.date(2008, i, 1).strftime('%B')) for i in range(1, 13)]
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["MAIL_SERVER"] = 'smtp.gmail.com'
app.config["MAIL_PORT"] = 587
app.config["MAIL_USERNAME"] = os.environ.get('EMAIL', 'gm.sobig@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('PASSWORD', 'eggpggxbfvykmtag')
app.config['MAIL_USE_TLS'] = True
app.config['JSON_SORT_KEYS'] = False
EMAIL = os.environ.get('EMAIL', 'gm.sobig@gmail.com')
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
                    base_url=None)
search = Search()
search.init_app(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# ------------------ END BLOCK ------------------

# ------------------ USER CONFIG ------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __searchable__ = ['name']
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(700), unique=True)
    confirmed_email = db.Column(db.Boolean(), default=False)
    join_date = db.Column(db.String(300), default='')
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    admin = db.Column(db.Boolean(), default=False)
    author = db.Column(db.Boolean(), default=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    api_key = relationship("ApiKey", back_populates="developer")
    deletion_report = relationship('DeletionReport', back_populates='user')


# ------------------ DATABASE CONFIG ------------------

# ------ DELETION REPORT TABLE ------

class DeletionReport(db.Model):
    __tablename__ = 'deletion_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates='deletion_report')
    deletion_reason = db.Column(db.String(1200), default='')
    deletion_explanation = db.Column(db.String(1200), default='')
    approval_link = db.Column(db.String(1000), default='')
    rejection_link = db.Column(db.String(1000), default='')
    date = db.Column(db.String(250), default='')


# ------ API KEY TABLE ------

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    developer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    developer = relationship("User", back_populates="api_key")
    occupation = db.Column(db.String(200), nullable=False)
    application = db.Column(db.String(1200), nullable=False)
    usage = db.Column(db.String(1200))
    api_key = db.Column(db.String(500), nullable=False)
    all_posts = db.Column(db.Integer, default=0)
    random_post = db.Column(db.Integer, default=0)
    all_users = db.Column(db.Integer, default=0)


# ------ END ------

# ------ BLOG POSTS TABLE ------

class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    __searchable__ = ["title", "subtitle"]
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(400), nullable=False)
    subtitle = db.Column(db.String(400), nullable=False)
    date = db.Column(db.String(400), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(600), nullable=True)
    comments = relationship("Comment", back_populates="parent_post")


# ------ END ------

# ------ COMMENTS TABLE ------

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates='comments')
    comment = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(250), nullable=False)


# ------ END ------


# ------ DELETED POSTS TABLE ------

class DeletedPost(db.Model):
    __tablename__ = 'deleted_posts'
    id = db.Column(db.Integer, primary_key=True)
    json_column = db.Column(JSON, nullable=False)


# ------ END ------


# ------ DELETED POSTS TABLE ------

class Data(db.Model):
    __tablename__ = 'data_table'
    id = db.Column(db.Integer, primary_key=True)
    json_column = db.Column(JSON, nullable=False)


# ------ END ------

db.create_all()  # CREATE ALL TABLES


# ------------------ END ------------------


def get_posts():  # GET ALL EXISTING POSTS
    try:
        return BlogPost.query.all()
    except OperationalError:
        return []


def get_user_api(user_id):
    try:
        requested_api = ApiKey.query.filter_by(developer_id=user_id).first()
    except AttributeError:
        return None
    if requested_api is not None:
        api_dict = {1: {"name": "API Info",
                        "description": "View your key Information.",
                        "Developer's Occupation": requested_api.occupation,
                        "Application": requested_api.application,
                        "API Usage": requested_api.usage,
                        "API Key": requested_api.api_key},
                    2: {"name": "API Requests",
                        "description": "Request statistics.",
                        "Total Requests": sum([requested_api.all_posts, requested_api.random_post,
                                               requested_api.all_users]),
                        "All Posts Requests": requested_api.all_posts,
                        "Random Post Requests": requested_api.random_post,
                        "All Users Requests": requested_api.all_users}}
        return api_dict
    return None


def get_deletion_report(user_id):
    try:
        requested_report = DeletionReport.query.filter_by(user_id=user_id).first()
    except AttributeError:
        return None
    if requested_report is not None:
        report_dict = {1: {"name": "Deletion Request Report",
                           "description": "View Report",
                           "Deletion Reason": requested_report.deletion_reason,
                           "Additional Information": requested_report.deletion_explanation,
                           "Submitted on": requested_report.date,
                           "approval": requested_report.approval_link,
                           "rejection": requested_report.rejection_link}}
        return report_dict
    return None


def clean_posts():
    [db.session.delete(post) for post in DeletedPost.query.all()
     if User.query.filter_by(email=post.json_column["author_email"]).first() is None]
    for post in BlogPost.query.all():
        try:
            user = User.query.filter_by(email=post.author.email).first()
            if user is None:
                db.session.delete(post)
        except AttributeError:
            db.session.delete(post)
    for comment in Comment.query.all():
        try:
            comment = comment.author.email
        except (AttributeError, TypeError):
            db.session.delete(comment)
    for api_key in ApiKey.query.all():
        try:
            key = api_key.developer.email
        except (AttributeError, TypeError):
            db.session.delete(api_key)
    for deletion_report in DeletionReport.query.all():
        try:
            report = deletion_report.user.email
        except (AttributeError, TypeError):
            db.session.delete(deletion_report)


def generate_date():  # GET THE CURRENT DATE IN A STRING FORMAT
    now = dt.datetime.now()
    current_month = [month for month in months if now.month == month[0]][0][1]
    return f'{current_month} {now.day}, {now.year}'


def get_user_posts(user_id):  # GET ALL POSTS ASSIGNED TO USER BY USER ID
    try:
        return User.query.get(user_id).posts
    except AttributeError:
        return []


def get_user_comments(user_id):  # GET ALL COMMENTS ASSIGNED TO USER BY USER ID
    try:
        return User.query.get(user_id).comments
    except AttributeError:
        return []


def delete_notification(email, name, action_user, action_title, action_reason):
    msg = Message('Account Deleted', sender=os.environ.get('EMAIL', EMAIL), recipients=[email])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was deleted by {action_user} due to "{action_title}".\n\n' \
               f'Deletion reasoning by actioning staff member:\n\n{html2text(action_reason)}\n\n' \
               f'If you believe that a mistake was made, contact us by replying to this email or via our website.'
    mail.send(msg)


def request_notification(email, name, decision):
    msg = Message('Deletion Request', sender=os.environ.get('EMAIL', EMAIL), recipients=[email])
    if decision:
        msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
                   f" events that occurred in regards to your account.\n\n" \
                   f"Your Deletion Request was {decision}.\n\n" \
                   f"If you believe that a mistake was made, please contact us by replying to this email or via our" \
                   f" website."
    mail.send(msg)


def set_notification(category, email, name, action_user, action_reason):
    try:
        support_email = get_data()["contact-configuration"]["support_email"]
    except KeyError:
        msg = Message(f'Account set as {category}', sender=os.environ.get('EMAIL', EMAIL), recipients=[email])
    else:
        msg = Message(f'Account set as {category}', sender=os.environ.get('EMAIL', EMAIL), recipients=[email,
                                                                                                       support_email])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was set as an {category} by {action_user}.\n\n' \
               f'Reasoning by actioning staff member:\n\n{html2text(action_reason)}\n\n' \
               f'Congratulations, if you have any inquires, contact us by replying to this email or via our website.'
    mail.send(msg)


def remove_notification(category, email, name, action_user, action_reason):
    try:
        support_email = get_data()["contact-configuration"]["support_email"]
    except KeyError:
        msg = Message(f'Account removed as {category}', sender=os.environ.get('EMAIL', EMAIL), recipients=[email])
    else:
        msg = Message(f'Account removed as {category}', sender=os.environ.get('EMAIL', EMAIL), recipients=[email,
                                                                                                           support_email
                                                                                                           ])
    msg.body = f"Hello {name}, this is an automatic email from {get_name()} to notify you of recent" \
               f" events that occurred in regards to your account.\n\n" \
               f'Your account was removed as an {category} by {action_user}.\n\n' \
               f'Reasoning by actioning staff member:\n\n{html2text(action_reason)}\n\n' \
               f'If you believe that a mistake was made, contact us by replying to this email or via our website.'
    mail.send(msg)


def contact_notification(email, name, action_reason):
    try:
        support_email = get_data()["contact_configuration"]["support_email"]
    except KeyError:
        return False
    msg = Message(f"{get_name()} - Contact Inquiry", sender=os.environ.get('EMAIL', EMAIL), recipients=[support_email])
    msg.body = f"This is an automatic email from {get_name()} to notify you of a" \
               f" user inquiry.\n\n" \
               f'Name: {name}\n\n' \
               f'Email: {email}\n\n' \
               f'Message:\n\n{html2text(action_reason)}' \
               f'Note: This email was set as a support email for {get_name()}, if you are not familiar with the' \
               f' source of this email, please contact us by replying to this email or via our website.'
    mail.send(msg)


def admin_redirect():
    if current_user.is_authenticated is False or current_user.admin is False:
        return abort(403)


def get_admin_count():  # GET THE AMOUNT OF ADMINISTRATORS
    return len([user for user in User.query.all() if user.admin is True])


def get_deleted():
    return [(post.id, post.json_column) for post in DeletedPost.query.all()]


def get_data(homepage=False):  # GET CONFIG DATA
    def set_default():
        default_data = {"secret_password": generate_password_hash(password="default",
                                                                  method='pbkdf2:sha256', salt_length=8),
                        "website_configuration": {
                            "name": "Website",
                            "homepage_title": "A website",
                            "homepage_subtitle": "A fully fledged website",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "twitter_link": "https://www.twitter.com",
                            "facebook_link": "https://www.facebook.com",
                            "github_link": "https://www.github.com"
                        },
                        "contact_configuration": {
                            "page_heading": "Contact us",
                            "page_subheading": "Contact us, and we'll respond as soon as we can.",
                            "page_description": "With the current workload, we are able to respond within 24 hours.",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "support_email": os.environ.get('EMAIL', EMAIL)
                        },
                        "about_configuration": {
                            "page_heading": "About us",
                            "page_subheading": "About what we do.",
                            "background_image": "https://www.panggi.com/images/featured/python.png",
                            "page_content": "For now, this page remains empty."
                        }
                        }
        update_data(default_data)

    try:
        data = Data.query.all()[0].json_column
        if homepage:
            title = data["website_configuration"]["homepage_title"]
            subtitle = data["website_configuration"]["homepage_subtitle"]
            return title, subtitle
        else:
            return data
    except (KeyError, TypeError, OperationalError):
        if homepage:
            title = "A website."
            subtitle = "A fully-fledged website."
            return title, subtitle
        else:
            return {}
    except (AttributeError, IndexError):
        set_default()
        if homepage:
            get_data(homepage=True)
        else:
            get_data()
        return redirect(url_for("home"))


def get_options(requested_page: int = 1, website=False):
    def get_last(given_options: dict):
        try:
            use_id = list(given_options.keys())[-1] + 1
        except IndexError:
            use_id = 1
        return use_id

    if website:
        if current_user.is_authenticated and current_user.admin is True:
            options_dict = {1: {"name": "Website Configuration",
                                "desc": "Configure your website.",
                                "func": "web_configuration"},
                            2: {"name": "Contact Me Configuration",
                                "desc": 'Configure the "Contact Me" page.',
                                "func": "contact_configuration"},
                            3: {"name": "About Me Configuration",
                                "desc": 'Configure the "About Me" page.',
                                "func": "about_configuration"},
                            4: {"name": "Authentication Configuration",
                                "desc": "Configure the website's authentication system.",
                                "func": "authentication_configuration"},
                            5: {"name": "User Database Table",
                                "desc": "Visualize your user database effortlessly.",
                                "func": "user_table"}
                            }
        else:
            return abort(403)
    else:
        if current_user.is_authenticated:
            options_dict = {}
            if check_api(current_user.id) is False:
                options_dict[get_last(options_dict)] = {"name": "Generate API Key",
                                                        "desc": "Generate an API Key to use our API services.",
                                                        "func": "generate_key"}
            if check_deletion(current_user.id) is False:
                options_dict[get_last(options_dict)] = {"name": "Delete my Account",
                                                        "desc": "Request account deletion",
                                                        "func": "request_deletion"}

        else:
            return abort(401)
    result = requested_page * 3
    if requested_page != 1:
        options = [options_dict[option] for i in range(result - 2, result + 1) for option in options_dict.keys()
                   if option == i]
    else:
        options = list(options_dict.values())[:3]

    return options


def update_data(given_data):  # UPDATE CONFIG DATA
    new_data = Data(json_column=given_data)
    if len(Data.query.all()) > 0 and Data.query.all()[0] is not None:
        db.session.delete(Data.query.all()[0])
    db.session.add(new_data)
    db.session.commit()


def get_post_dict(post):
    post_dict = {"post": {"author": post.author.name,
                          "title": post.title,
                          "subtitle": post.subtitle,
                          "published_on": post.date,
                          "contents": html2text(post.body).strip(),
                          "img_url": post.img_url,
                          "comments": [(comment.author.name, html2text(comment.comment).strip()) for comment
                                       in post.comments]
                          }}
    return post_dict


def generate_new():
    def get_new():
        new = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        return new

    while True:
        new_key = get_new()
        if any([key.api_key for key in ApiKey.query.all() if key == new_key]):
            new_key = get_new()
        else:
            break
    return new_key


def check_api(user_id):
    return ApiKey.query.filter_by(developer_id=user_id).first() is not None


def check_deletion(user_id):
    return DeletionReport.query.filter_by(user_id=user_id).first() is not None


def validate_key(api_key):
    return any([key for key in ApiKey.query.all() if api_key == key.api_key])


def get_users_filter(view_filter=None):
    if view_filter == 'admin':
        users = User.query.filter_by(admin=True).all()
    elif view_filter == 'author':
        users = User.query.filter_by(author=True).all()
    elif view_filter == 'registered':
        users = User.query.filter_by(confirmed_email=True).all()
    elif view_filter == 'unconfirmed':
        users = User.query.filter_by(confirmed_email=False).all()
    elif view_filter == 'pending':
        users = [user for user in User.query.all()
                 if DeletionReport.query.filter_by(user_id=user.id).first() is not None]
    else:
        users = User.query.all()
    return users


def get_user_dict(users):
    user_dict = {users.index(user) + 1: {"id": user.id,
                                         "email": user.email,
                                         "username": user.name,
                                         "posts_num":
                                             len(user.posts),
                                         "is_developer": check_api(user.id),
                                         "pending_deletion": check_deletion(user.id),
                                         "permissions": [
                                             "Administrator" if user.admin is True else "Author" if user.author is True
                                             else "Developer" if check_api(user.id) else
                                             "Registered User" if user.confirmed_email is True else None][0],
                                         "confirmed": user.confirmed_email,
                                         "joined_on": user.join_date} for user in users}
    return user_dict


def check_errors():  # CHECK FOR ERRORS IN DATA
    errors = {}

    # ------ TEST 1, CHECK IF DATA FILE IS EMPTY ------

    try:
        test = Data.query.all()[0].json_column
    except (AttributeError, IndexError):
        errors["Data File"] = "Data file is empty, no website configurations available."
    else:
        if check_password_hash(test['secret_password'], 'default'):
            errors["Authentication Password"] = "Authentication Password is set to default, change it immediately."

    # ------ TEST END ------

    return errors


def get_name():
    data = get_data()
    try:
        return data["website_configuration"]["name"]
    except (TypeError, IndexError, KeyError):
        return "Website"


def get_background(configuration="none"):
    try:
        return get_data()[configuration]["background_image"]
    except (KeyError, TypeError):
        return ""


# ------------------ END BLOCK ------------------

# ------------------ ERROR HANDLERS ------------------

@app.errorhandler(401)
def unauthorized(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="401 - Unauthorized", error_description="You're unauthorized to perform this action.",
                           name=get_name()), 401


@app.errorhandler(403)
def forbidden(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="403 - Forbidden", error_description="You're unauthorized to perform this action.",
                           name=get_name()), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="404 - Page Not Found", error_description="Page not found.",
                           name=get_name()), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('http-error.html', background_image=get_background('website_configuration'),
                           error="500 - Internal Server Error", error_description="An error has occurred on our side,"
                                                                                  "we apologize for the inconvenience.",
                           name=get_name()), 500


# ------------------ END ------------------


# ------------------ FORMS ------------------


# ------ CREATE POST FORM ------

class CreatePostForm(FlaskForm):
    title = StringField("Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField("Post Image URL")
    body = CKEditorField("Post Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ WEB CONFIGURATION FORM ------

class WebConfigForm(FlaskForm):
    name = StringField("Website Name", validators=[DataRequired()],
                       render_kw={"style": "margin-bottom: 10px;"})
    homepage_title = StringField("Homepage Title", validators=[DataRequired()],
                                 render_kw={"style": "margin-bottom: 10px;"})
    homepage_subtitle = StringField("Homepage Subtitle", validators=[DataRequired()],
                                    render_kw={"style": "margin-bottom: 10px;"})
    background_image = StringField("Background Image URL",
                                   render_kw={"style": "margin-bottom: 10px;"})
    twitter_link = StringField("Twitter Link", validators=[DataRequired(), URL()],
                               render_kw={"style": "margin-bottom: 10px;"})
    facebook_link = StringField("FaceBook Link", validators=[DataRequired(), URL()],
                                render_kw={"style": "margin-bottom: 10px;"})
    github_link = StringField("GitHub Link", validators=[DataRequired(), URL()],
                              render_kw={"style": "margin-bottom: 10px;"})
    submit = SubmitField("Save Changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ REGISTER FORM ------

class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign up", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ LOGIN FORM ------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in", render_kw={"style": "margin-top: 25px;"})


# ------ END ------

# ------ CONTACT FORM ------

class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    message = CKEditorField("Your Message", validators=[DataRequired()])
    submit = SubmitField("Send", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ COMMENT FORM ------

class CommentForm(FlaskForm):
    comment = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ SEARCH FORM ------

class SearchForm(FlaskForm):
    category = SelectField("Category", choices=[('posts', 'Posts'), ('users', 'Users')])
    search = StringField("Search", validators=[DataRequired()])
    submit = SubmitField("Search", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ DELETION REPORT FORM ------

class DeleteForm(FlaskForm):
    title = StringField("Action Title", validators=[DataRequired()])
    reason = CKEditorField("Action Reason", validators=[DataRequired()])
    submit = SubmitField("Delete Account", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ DELETION REPORT FORM ------

class AuthForm(FlaskForm):
    code = PasswordField("Authorization Code", validators=[DataRequired()])
    submit = SubmitField("Authenticate", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------ CONTACT CONFIG FORM ------

class ContactConfigForm(FlaskForm):
    page_heading = StringField("Contact Page Title", validators=[DataRequired()])
    page_subheading = StringField("Contact Page Subtitle", validators=[DataRequired()])
    page_description = StringField("Contact Page Description", validators=[DataRequired()])
    background_image = StringField("Contact Page Background Image", validators=[URL()])
    support_email = StringField("Contact Support Email (Inquires will be directed to the specified email)",
                                validators=[DataRequired(), Email()])
    submit = SubmitField("Save changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------ CONTACT CONFIG FORM ------

class AboutConfigForm(FlaskForm):
    page_heading = StringField("About Page Title", validators=[DataRequired()])
    page_subheading = StringField("About Page Subtitle", validators=[DataRequired()])
    background_image = StringField("Contact Page Background Image", validators=[URL()])
    page_content = CKEditorField("About Page Content", validators=[DataRequired()])
    submit = SubmitField("Save changes", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ MAKE ADMINISTRATOR FORM ------

class MakeUserForm(FlaskForm):
    reason = CKEditorField("Reason for Action", validators=[DataRequired()])
    submit = SubmitField("Proceed", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ AUTHENTICATION CONFIG FORM ------

class AuthConfig(FlaskForm):
    old_password = PasswordField("Old Authentication Password", validators=[DataRequired()])
    new_password = PasswordField("New Authentication Password", validators=[DataRequired()])
    submit = SubmitField("Change Authentication Password", render_kw={"style": "margin-top: 20px;"})


# ------ END ------

# ------ API KEY GENERATOR FORM ------

class ApiGenerate(FlaskForm):
    occupation = SelectField("What are you?", choices=[('Student', 'Student'), ('Professional Developer',
                                                                                'Professional Developer'),
                                                       ('Hobbyist', 'Hobbyist'), ('Other', 'Other')])
    application = StringField("Tell us about your application in short.", validators=[DataRequired()])
    usage = CKEditorField("What will you be using our API service for?", validators=[DataRequired()])
    submit = SubmitField("Generate API Key", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------ DELETION REQUEST FORM ------

class DeletionRequest(FlaskForm):
    reason = SelectField("Why are you deleting your account?", choices=[('Dissatisfied', 'Dissatisfied'),
                                                                        ('Not Interested', 'Not Interested'),
                                                                        ("Bad User Experience", "Bad User Experience"),
                                                                        ('Other', 'Other')])
    explanation = CKEditorField("Could you tell us more?")
    submit = SubmitField("Delete my account", render_kw={"style": "margin-top: 20px;"})


# ------ END ------


# ------------------ END BLOCK ------------------


# ------------------ WRAPPER BLOCK ------------------


def logout_required(func):
    """Checks whether user is logged out or raises error 401."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated:
            abort(401)
        return func(*args, **kwargs)

    return wrapper


def admin_only(func):
    """Checks whether user is admin or raises error 403."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated is False or current_user.admin is False:
            abort(403)
        return func(*args, **kwargs)

    return wrapper


def staff_only(func):
    """Checks whether a user is a staff member or raises 403 error."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated is False:
            abort(403)
        if current_user.admin is False and current_user.author is False:
            abort(403)
        return func(*args, **kwargs)

    return wrapper


# ------------------ END BLOCK ------------------


# ------------------ PAGES BLOCK ------------------

@app.route('/')
def home():
    try:
        data = get_data(homepage=True)
    except OperationalError:
        db.create_all()
    return render_template("index.html", all_posts=get_posts()[:3], posts_count=len(get_posts()), current_id=1,
                           title=data[0], subtitle=data[1], name=get_name(),
                           background_image=get_background("website_configuration"))


@app.route('/page/<int:page_id>')
def page(page_id):
    deleted = request.args.get('deleted')
    user_id = request.args.get('user_id')
    current_mode = request.args.get('current_mode')
    table_page = request.args.get('table_page')
    view_filter = request.args.get('view_filter')
    settings_view = request.args.get('settings')
    mode = request.args.get('mode')
    data = get_data(homepage=True)
    if deleted == 'True':
        blog_posts = get_deleted()
        if page_id == 1:
            return redirect(url_for('deleted_posts'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
        return render_template('index.html', deleted_posts=posts, deleted='True',
                               posts_count=count, current_id=page_id, name=get_name(),
                               background_image=get_background('website_configuration'), title="Deleted Posts",
                               subtitle="View and recover deleted posts!")
    elif user_id is not None and User.query.get(user_id) is not None:
        user = User.query.get(user_id)
        posts = get_user_posts(user_id)
        comments = get_user_comments(user_id)
        if current_mode in ['posts', 'comments', 'api']:
            if current_mode == 'posts':
                blog_posts = posts
                if page_id == 1:
                    return redirect(url_for('user_page', user_id=user_id))
                result = page_id * 3
                posts = blog_posts[result - 3:result]
                count = 0
                for _ in posts:
                    count += 1
                return render_template("user.html", all_posts=posts, posts_count=count, current_id=page_id,
                                       title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Posts",
                                       name=get_name(),
                                       background_image=get_background('website_configuration'), current_mode='posts',
                                       user=user)
            elif current_mode == 'comments':
                blog_posts = comments
                if page_id == 1:
                    return redirect(url_for('user_page', user_id=user_id, current_mode='comments'))
                result = page_id * 3
                posts = blog_posts[result - 3:result]
                count = 0
                for _ in posts:
                    count += 1
                return render_template("user.html", comments=posts, posts_count=count,
                                       current_id=page_id,
                                       title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Comments",
                                       name=get_name(),
                                       background_image=get_background('website_configuration'),
                                       current_mode='comments', user=user)
            elif current_mode == 'api':
                requested_api = get_user_api(user_id)
                if page_id == 1:
                    return redirect(url_for('user_page', user_id=user_id, current_mode='api'))
                if requested_api is not None:
                    if current_user.email == ApiKey.query.filter_by(developer_id=user_id).first().developer.email \
                            or current_user.admin is True:
                        try:
                            return render_template("user.html", all_posts=requested_api[page_id],
                                                   current_id=page_id,
                                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s API Key",
                                                   name=get_name(),
                                                   background_image=get_background('website_configuration'),
                                                   current_mode='api',
                                                   user=user, posts_count=len(requested_api[page_id]),
                                                   admin_count=get_admin_count())
                        except (KeyError, IndexError):
                            return render_template("user.html", all_posts={},
                                                   current_id=page_id,
                                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s API Key",
                                                   name=get_name(),
                                                   background_image=get_background('website_configuration'),
                                                   current_mode='api',
                                                   user=user, posts_count=0,
                                                   admin_count=get_admin_count())
                    else:
                        if current_user.is_authenticated:
                            return abort(403)
                        else:
                            return abort(401)
                else:
                    flash("Could not find an API with the specified ID.")
                    return redirect(url_for(user_page, user_id=user_id))
        else:
            flash("Malformed page request for user profile.")
            return redirect(url_for('home'))
    elif table_page is not None:
        users_filter = get_users_filter(view_filter)
        blog_posts = list(get_user_dict(users_filter).values())
        if page_id == 1:
            return redirect(url_for('user_table', view_filter=view_filter))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
        return render_template('index.html', users=posts, user_table="True",
                               posts_count=count, current_id=page_id, name=get_name(), title="User Database Table",
                               subtitle="Visualize your user database effortlessly.",
                               background_image=get_background('website_configuration'),
                               unconfirmed=any(User.query.filter_by(confirmed_email=False).all()),
                               current_view=view_filter)
    elif settings_view is not None:
        if mode != 'admin':
            if current_user.is_authenticated:
                options = get_options(requested_page=page_id)
                errors = {}
                title = "Account Settings"
                subtitle = 'Here you will be able to configure your account settings.'
            else:
                return abort(401)
        else:
            if current_user.is_authenticated and current_user.admin is True:
                options = get_options(requested_page=page_id, website=True)
                errors = check_errors()
                title = "Settings"
                subtitle = "Here you will be able to access primary website configurations."
            else:
                return abort(403)
        count = 0
        if page_id == 1:
            return redirect(url_for('settings', mode=mode))
        for _ in options:
            count += 1
        return render_template('index.html', settings="True", options=options,
                               options_count=len(options),
                               errors=errors, title=title,
                               subtitle=subtitle,
                               name=get_name(),
                               background_image=get_background('website_configuration'), current_id=page_id,
                               posts_count=count, mode=mode)
    else:
        blog_posts = get_posts()
        if page_id == 1:
            return redirect(url_for('home'))
        result = page_id * 3
        posts = blog_posts[result - 3:result]
        count = 0
        for _ in posts:
            count += 1
    return render_template("index.html", all_posts=posts, posts_count=count, current_id=page_id,
                           name=get_name(),
                           background_image=get_background('website_configuration'), title=data[0],
                           subtitle=data[1])


@app.route("/about")
def about():
    try:
        about_config = get_data()['about_configuration']
    except KeyError:
        heading = "About us"
        subheading = "About what we do."
        content = "For now, this page remains empty."
    else:
        heading = about_config['page_heading']
        subheading = about_config['page_subheading']
        content = about_config['page_content']
    return render_template("about.html", heading=heading, subheading=subheading, content=content,
                           background_image=get_background('about_configuration'), name=get_name())


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    valid = True
    try:
        support_email = get_data()["contact_configuration"]["support_email"]
    except KeyError:
        flash("Warning | No support email specified, messages will not be received.")
        valid = False
    try:
        contact_config = get_data()['contact_configuration']
    except KeyError:
        heading = "Contact us"
        subheading = "We'll get to you as soon as we can."
        description = "Want to get in touch? Fill out the form below and we'll respond as soon as we can!"
    else:
        heading = contact_config['page_heading']
        subheading = contact_config['page_subheading']
        description = contact_config['page_description']
    if valid:
        if current_user.is_authenticated and current_user.confirmed_email:
            form = ContactForm(name=current_user.name, email=current_user.email)
        else:
            form = ContactForm()
        if form.validate_on_submit():
            notification = contact_notification(form.email.data, form.name.data, form.message.data)
            if notification is False:
                flash("No support email specified, unable to send your message.")
                return redirect(url_for('home'))
            else:
                flash("Message successfully sent.")
                return redirect(url_for('home'))
        return render_template("contact.html", form=form, heading=heading, subheading=subheading,
                               description=description,
                               background_image=get_background('contact_configuration'), name=get_name())
    return render_template("contact.html", heading=heading, subheading=subheading,
                           description=description,
                           background_image=get_background('contact_configuration'), name=get_name())


# ------------------ END BLOCK ------------------


# ------------------ POST SYSTEM BLOCK ------------------

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchForm()
    if form.validate_on_submit():
        if form.category.data == 'posts':
            posts = BlogPost.query.msearch(form.search.data).all()
            return render_template("index.html", all_posts=posts[:3], posts_count=len(posts), current_id=1,
                                   title="Search Results",
                                   subtitle=f"Displaying post search results for: {form.search.data}",
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   search=True, mode='posts')
        else:
            users = [user for user in User.query.msearch(form.search.data).all() if user.confirmed_email is True]
            return render_template("index.html", results=users[:3], posts_count=len(users), current_id=1,
                                   title="Search Results",
                                   subtitle=f"Displaying user search results for: {form.search.data}",
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   search=True, mode='users')
    return render_template('search.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    deleted = request.args.get('deleted')
    comment_page = request.args.get('c_page')
    form = CommentForm()
    if deleted is None:
        requested_post = BlogPost.query.get(post_id)
        post_comments = BlogPost.query.get(post_id).comments
    else:
        try:
            requested_post = (DeletedPost.query.get(post_id).id, DeletedPost.query.get(post_id).json_column)
        except AttributeError:
            flash("Could not find a post with the specified ID.")
            return redirect(url_for('deleted_posts'))
        post_comments = requested_post[1]["comments"]
    if comment_page is not None:
        current_c = comment_page
        if comment_page == 1:
            return redirect(url_for('show_post', post_id=post_id))
        try:
            result = int(comment_page) * 3
        except TypeError:
            return redirect(url_for('show_post', post_id=post_id))
        comment_items = post_comments[result - 3:result]
    else:
        current_c = 1
        if deleted is None:
            comment_items = requested_post.comments[:3]
        else:
            comment_items = requested_post[1]["comments"][:3]

    count = 0
    for _ in comment_items:
        count += 1

    if form.validate_on_submit():
        if current_user.is_authenticated:
            now = dt.datetime.now()
            current_month = [month for month in months if now.month == month[0]][0][1]
            date = f'{current_month} {now.day}, {now.year}'
            new_comment = Comment(author=current_user,
                                  parent_post=requested_post,
                                  comment=form.comment.data,
                                  date=date)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
        else:
            flash("User is not logged in.")
            return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, deleted=str(deleted),
                           name=get_name(), form=form, comments=comment_items, current_c=int(current_c), c_count=count)


@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@staff_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    if post is not None:
        if post.author.email == current_user.email:
            form = CreatePostForm(title=post.title,
                                  subtitle=post.subtitle,
                                  img_url=post.img_url,
                                  body=post.body)
            if form.validate_on_submit():
                post.title = form.title.data
                post.subtitle = form.subtitle.data
                post.img_url = form.img_url.data
                post.body = form.body.data
                db.session.commit()
                return redirect(url_for('show_post', post_id=post_id))
            return render_template('make-post.html', edit=True, post=post, form=form, name=get_name())
        else:
            return abort(403)
    else:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('home'))


@app.route('/add', methods=['GET', 'POST'])
@staff_only
def add_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        date = generate_date()
        new_post = BlogPost(title=form.title.data,
                            subtitle=form.subtitle.data,
                            author=current_user,
                            img_url=form.img_url.data,
                            body=form.body.data,
                            date=date)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('make-post.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/deleted')
@staff_only
def deleted_posts():
    posts = get_deleted()[:3]
    return render_template('index.html', deleted_posts=posts,
                           deleted="True",
                           posts_count=len(posts), current_id=1, name=get_name(),
                           background_image=get_background('website_configuration'), title="Deleted Posts",
                           subtitle="View and recover deleted posts!")


@app.route('/delete/<int:post_id>')
@staff_only
def delete_post(post_id):
    post = BlogPost.query.get(post_id)
    if post is not None:
        if current_user.is_authenticated and current_user.author is True and post.author.email == current_user.email \
                or current_user.is_authenticated and current_user.admin is True:
            try:
                lst = Comment.query.filter_by(post_id=post.id).all()
            except AttributeError:
                flash("Could not find a post with the specified ID.")
                return redirect(url_for('deleted_posts'))
            new_post = {
                "post_title": post.title,
                "author_id": post.author.id,
                "author_email": post.author.email,
                "author": post.author.name,
                "subtitle": post.subtitle,
                "img_url": post.img_url,
                "body": post.body,
                "date": post.date,
                "comments": [{"author_id": comment.author_id, "author": comment.author.name,
                              "author_email": comment.author.email, "post_id": comment.post_id,
                              "comment": comment.comment,
                              "date": comment.date} for comment in lst]
            }
            new_deleted = DeletedPost(json_column=new_post)
            db.session.add(new_deleted)
            [db.session.delete(comment) for comment in lst]
            db.session.delete(post)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            return abort(403)
    else:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))


@app.route('/recover/<int:post_id>')
@staff_only
def recover_post(post_id):
    try:
        actual = DeletedPost.query.get(post_id)
        post = actual.json_column
    except AttributeError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    try:
        if current_user.email != post["author_email"] or current_user.author is False and current_user.admin is False:
            return abort(403)
    except AttributeError:
        flash("The author could not be found.")
        return redirect(url_for('deleted_posts'))
    comments = post["comments"]
    new_post = BlogPost(author=User.query.filter_by(email=post["author_email"]).first(),
                        title=post["post_title"],
                        subtitle=post["subtitle"],
                        date=post["date"],
                        body=post["body"],
                        img_url=post["img_url"],
                        )
    db.session.add(new_post)
    [db.session.add(Comment(author=User.query.filter_by(email=comment["author_email"]).first(),
                            post_id=new_post.id,
                            parent_post=new_post,
                            comment=comment["comment"], date=comment["date"])) for comment in comments]
    db.session.delete(actual)
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/perm-delete/<int:post_id>')
@admin_only
def perm_delete(post_id):
    try:
        actual_post = DeletedPost.query.get(post_id)
        post = actual_post.json_column
    except AttributeError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    try:
        db.session.delete(actual_post)
    except UnmappedInstanceError:
        flash("Could not find a post with the specified ID.")
        return redirect(url_for('deleted_posts'))
    db.session.commit()
    return redirect(url_for('deleted_posts'))


# ------ COMMENT SYSTEM ------


@app.route('/delete-comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    if comment is not None:
        if comment.parent_post.author.email == current_user.email or current_user.email == comment.author.email:
            current_post = comment.post_id
            db.session.delete(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=current_post))
        else:
            return abort(403)
    else:
        flash("Could not find a comment with the specified ID.")
        return redirect(url_for('home'))


# ------ END ------


# ------------------ END BLOCK ------------------


# ------------------ SETTINGS BLOCK ------------------

@app.route('/settings')
@login_required
def settings():
    mode = request.args.get('mode')
    if mode != 'admin':
        options = get_options()
        title = "Account Settings"
        subtitle = "Here you will be able to configure your account settings."
        errors = {}
    else:
        if current_user.admin is True:
            options = get_options(website=True)
            title = "Settings"
            subtitle = "Here you will be able to access primary website configurations."
            errors = check_errors()
        else:
            abort(403)
    return render_template('index.html', settings="True", options=options,
                           posts_count=len(options),
                           errors=errors, title=title,
                           subtitle=subtitle,
                           name=get_name(),
                           background_image=get_background('website_configuration'), current_id=1, mode=mode)


@app.route('/web-configure', methods=['GET', 'POST'])
@admin_only
def web_configuration():
    data = get_data()
    try:
        config_data = data['website_configuration']
        form = WebConfigForm(name=config_data['name'],
                             homepage_title=config_data['homepage_title'],
                             homepage_subtitle=config_data['homepage_subtitle'],
                             background_image=config_data['background_image'],
                             twitter_link=config_data['twitter_link'],
                             facebook_link=config_data['facebook_link'],
                             github_link=config_data['github_link'])
    except KeyError:
        form = WebConfigForm()
    if form.validate_on_submit():
        new_data = {"website_configuration": {
            "name": form.name.data,
            "homepage_title": form.homepage_title.data,
            "homepage_subtitle": form.homepage_subtitle.data,
            "background_image": form.background_image.data,
            "twitter_link": form.twitter_link.data,
            "facebook_link": form.facebook_link.data,
            "github_link": form.github_link.data
        }
        }
        data.update(new_data)
        update_data(data)
        return redirect(url_for('settings', mode='admin'))
    return render_template('config.html', config_title="Website Configuration",
                           config_desc="Configure primary website elements.", form=form,
                           config_func="web_configuration", name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/contact-configure', methods=['GET', 'POST'])
@admin_only
def contact_configuration():
    data = get_data()
    try:
        config_data = data['contact_configuration']
        form = ContactConfigForm(page_heading=config_data['page_heading'],
                                 page_subheading=config_data['page_subheading'],
                                 page_description=config_data['page_description'],
                                 background_image=config_data['background_image'],
                                 support_email=config_data['support_email'])
    except KeyError:
        form = ContactConfigForm()
    if form.validate_on_submit():
        new_data = {"contact_configuration": {
            "page_heading": form.page_heading.data,
            "page_subheading": form.page_subheading.data,
            "page_description": form.page_description.data,
            "background_image": form.background_image.data,
            "support_email": form.support_email.data
        }
        }
        data.update(new_data)
        update_data(data)
        return redirect(url_for('settings', mode='admin'))
    return render_template('config.html', config_title="Contact Page Configuration",
                           config_desc="Configure primary elements of the contact page.", form=form,
                           config_func="contact_configuration", name=get_name(),
                           background_image=get_background('contact_configuration'))


@app.route('/about-configure', methods=['GET', 'POST'])
@admin_only
def about_configuration():
    data = get_data()
    try:
        config_data = data['about_configuration']
        form = AboutConfigForm(page_heading=config_data['page_heading'],
                               page_subheading=config_data['page_subheading'],
                               background_image=config_data['background_image'],
                               page_content=config_data['page_content'])
    except KeyError:
        form = AboutConfigForm()
    if form.validate_on_submit():
        new_data = {"about_configuration": {
            "page_heading": form.page_heading.data,
            "page_subheading": form.page_heading.data,
            "page_content": form.page_content.data
        }
        }
        data.update(new_data)
        update_data(data)
        return redirect(url_for('settings', mode='admin'))
    return render_template('config.html', config_title="About Page Configuration",
                           config_desc="Configure primary elements of the about page.", form=form,
                           config_func="about_configuration", name=get_name(),
                           background_image=get_background('about_configuration'))


@app.route('/auth-configure', methods=['GET', 'POST'])
@admin_only
def authentication_configuration():
    form = AuthConfig()
    data = get_data()
    try:
        config_data = data['secret_password']
    except KeyError:
        config_data = None
    if form.validate_on_submit():
        if config_data is not None:
            try:
                if check_password_hash(config_data, form.old_password.data):
                    new_password = generate_password_hash(password=form.new_password.data,
                                                          method='pbkdf2:sha256', salt_length=8)
                    new_data = {"secret_password": new_password}
                    data.update(new_data)
                    update_data(data)
                    return redirect(url_for('settings'))
                else:
                    flash("Incorrect authentication password.")
            except TypeError:
                flash("An unexpected error occurred during verification handling.")
        else:
            new_password = generate_password_hash(password=form.new_password.data,
                                                  method='pbkdf2:sha256', salt_length=8)
            new_data = {"secret_password": new_password}
            data.update(new_data)
            update_data(data)
            return redirect(url_for('settings', mode='admin'))
    return render_template('config.html', config_title="Authentication Configuration",
                           config_desc="Configure primary elements of the website's authentication", form=form,
                           config_func="authentication_configuration", name=get_name(),
                           background_image=get_background('website_configuration'))


# ------------------ END BLOCK ------------------


# ------------------ USER BLOCK ------------------


@app.route('/user-table')
@admin_only
def user_table():
    view_filter = request.args.get('view_filter')
    users = get_users_filter(view_filter)
    user_dict = get_user_dict(users)
    return render_template('index.html', users=list(user_dict.values())[:3],
                           background_image=get_background('website_configuration'),
                           name=get_name(), current_id=1, user_table="True", title="User Database Table",
                           subtitle="Visualize your user database effortlessly.",
                           posts_count=len(list(user_dict.values())),
                           current_view=view_filter, unconfirmed=any(User.query.filter_by(confirmed_email=False).all()))


@app.route('/delete-unconfirmed')
@admin_only
def delete_unconfirmed():
    unconfirmed = User.query.filter_by(confirmed_email=False).all()
    if any(unconfirmed):
        [db.session.delete(user) for user in unconfirmed]
        flash("All unconfirmed users have been deleted from the user database.")
        db.session.commit()
    else:
        flash("No unconfirmed users in the database.")
    return redirect(url_for("user_table"))


@app.route('/admin/<int:user_id>', methods=['GET', 'POST'])
@login_required
def make_admin(user_id):
    if get_admin_count() > 0:
        admin_redirect()
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    form = MakeUserForm()
    if user is not None:
        if user.admin is not True:
            if authorized != "True":
                return redirect(url_for('admin_auth', user_id=user_id))
            if form.validate_on_submit():
                set_notification('administrator', user.email, user.name, current_user.name, form.reason.data)
                user.author = False
                user.admin = True
                db.session.commit()
                flash("The user has been set as an administrator, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='admin')
        else:
            flash("This user is already an administrator.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/admin-remove/<int:user_id>', methods=['GET', 'POST'])
@admin_only
def remove_admin(user_id):
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    form = MakeUserForm()
    if user is not None:
        if user.admin is True:
            if authorized != "True":
                return redirect(url_for('admin_auth', user_id=user_id, remove=True))
            if form.validate_on_submit():
                remove_notification('administrator', user.email, user.name, current_user.name, form.reason.data)
                user.admin = False
                db.session.commit()
                flash("The user has been removed as an administrator, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='admin', remove="True")
        else:
            flash("This user is not an administrator.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/author/<int:user_id>', methods=['GET', 'POST'])
@admin_only
def make_author(user_id):
    user = User.query.get(user_id)
    form = MakeUserForm()
    if user is not None:
        if user.author is not True:
            if form.validate_on_submit():
                set_notification('author', user.email, user.name, current_user.name, form.reason.data)
                user.author = True
                db.session.commit()
                flash("This user has been set as an author, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='author')
        else:
            flash("This user is already set as an author.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/author-remove/<int:user_id>', methods=['GET', 'POST'])
@admin_only
def remove_author(user_id):
    user = User.query.get(user_id)
    form = MakeUserForm()
    if user is not None:
        if user.author is True:
            if form.validate_on_submit():
                remove_notification('author', user.email, user.name, current_user.name, form.reason.data)
                user.author = False
                db.session.commit()
                flash("This user has been removed as an author, a notification has been sent to the user.")
                return redirect(url_for('user_page', user_id=user_id))
            return render_template('admin-form.html', form=form, user_name=user.name, user_id=user_id,
                                   name=get_name(), background_image=get_background('website_configuration'),
                                   category='author', remove="True")
        else:
            flash("This user is not an author.")
            return redirect(url_for('user_page', user_id=user_id))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/user/<int:user_id>')
def user_page(user_id):
    user = User.query.get(user_id)
    posts = get_user_posts(user_id)
    comments = get_user_comments(user_id)
    current_mode = request.args.get('current_mode')
    admin_count = get_admin_count()
    if user is not None:
        if current_mode == 'comments':
            return render_template("user.html", comments=comments[:3], posts_count=len(comments[:3]), current_id=1,
                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Comments", name=get_name(),
                                   background_image=get_background('website_configuration'), current_mode='comments',
                                   user=user, api_exists=check_api(user_id), report_exists=check_deletion(user_id),
                                   admin_count=admin_count)
        elif current_mode == 'posts' or current_mode is None:
            return render_template("user.html", all_posts=posts[:3], posts_count=len(posts[:3]), current_id=1,
                                   title=f"{user.name}'s Profile", subtitle=f"{user.name}'s Posts", name=get_name(),
                                   background_image=get_background('website_configuration'), current_mode='posts',
                                   user=user, report_exists=check_deletion(user_id),
                                   admin_count=admin_count,
                                   api_exists=check_api(user_id))
        elif current_mode == 'api':
            if current_user.is_authenticated and current_user.email == User.query.get(user_id).email \
                    or current_user.admin is True:
                requested_api = get_user_api(user_id)
                if requested_api is not None:
                    return render_template("user.html", all_posts=requested_api[1],
                                           current_id=1,
                                           title=f"{user.name}'s Profile", subtitle=f"{user.name}'s API Key",
                                           name=get_name(),
                                           background_image=get_background('website_configuration'),
                                           current_mode='api',
                                           user=user, posts_count=1, report_exists=check_deletion(user_id),
                                           admin_count=admin_count)
                else:
                    flash("Could not find an API key with the specified ID.")
                    return redirect(url_for('home'))
            else:
                if current_user.is_authenticated:
                    return abort(403)
                else:
                    return abort(401)
        elif current_mode == 'delete-report':
            if current_user.is_authenticated and current_user.email == User.query.get(user_id).email \
                    or current_user.admin is True:
                requested_report = get_deletion_report(user_id)
                if requested_report is not None:
                    return render_template("user.html", all_posts=requested_report[1],
                                           current_id=1,
                                           title=f"{user.name}'s Profile", subtitle=f"{user.name}'s"
                                                                                    f" Deletion Request Report",
                                           name=get_name(),
                                           background_image=get_background('website_configuration'),
                                           current_mode='delete-report',
                                           user=user, posts_count=1, api_exists=check_api(user_id),
                                           admin_count=admin_count)
                else:
                    flash("Could not find a deletion report with the specified ID.")
                    return redirect(url_for('home'))
        else:
            return abort(404)
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/delete-user/<int:user_id>', methods=['GET', 'POST'])
@admin_only
def delete_user(user_id):
    user = User.query.get(user_id)
    authorized = request.args.get('authorized')
    if user is not None:
        if user.admin is True and authorized != "True":
            return redirect(url_for('authorization', user_id=user_id))
        form = DeleteForm()
        if form.validate_on_submit():
            email = user.email
            delete_notification(email=user.email, name=user.name, action_user=current_user.name,
                                action_title=form.title.data, action_reason=form.reason.data)
            if current_user == user:
                logout_user()
            flash("The user has been deleted, a notification has been sent to the user.")
            db.session.delete(user)
            clean_posts()
            db.session.commit()
            return redirect(url_for('home'))
        return render_template('delete.html', form=form, user_id=user_id, name=get_name(), user_name=user.name,
                               background_image=get_background('website_configuration'))

    else:
        flash("This user does not exist.")
        return redirect(url_for('home'))


# ------------------ DELETION REQUEST BLOCK ------------------

@app.route('/finalize-deletion/<int:user_id>')
@login_required
def generate_deletion(user_id):
    user = User.query.get(user_id)
    if user is not None:
        if current_user.is_authenticated and current_user.email == user.email:
            if check_deletion(user_id) is True:
                requested_report = DeletionReport.query.filter_by(user_id=user_id).first()
                if requested_report.approval_link == '':
                    token = serializer.dumps(user.email, salt='deletion_request')
                    approval_link = url_for('handle_request', token=token, email=user.email, decision='approved',
                                            _external=True)
                    another_token = serializer.dumps(user.email, salt='deletion_request')
                    rejection_link = url_for('handle_request', token=another_token, email=user.email,
                                             decision='rejected', _external=True)
                    try:
                        requested_report.approval_link = approval_link
                        requested_report.rejection_link = rejection_link
                        requested_report.date = generate_date()
                    except AttributeError:
                        return abort(500)
                    else:
                        db.session.commit()
                        flash("Request sent, please wait 1-3 days for administrators to review your request.")
                        return redirect(url_for('home'))
                else:
                    flash("Your account is already in a pending deletion state.")
                    return redirect(url_for('home'))
            else:
                return abort(500)
        else:
            return abort(403)
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/request-deletion', methods=['GET', 'POST'])
@login_required
def request_deletion():
    requested_user = User.query.filter_by(email=current_user.email).first()
    form = DeletionRequest()
    if requested_user is not None:
        if current_user.is_authenticated and current_user.email == requested_user.email:
            if form.validate_on_submit():
                if get_admin_count() < 1:
                    request_notification(email=requested_user.email, name=requested_user.name, decision="approved")
                    if current_user == requested_user:
                        logout_user()
                    db.session.delete(requested_user)
                    db.session.commit()
                    flash("Your account has been successfully deleted.")
                    return redirect(url_for('home'))
                else:
                    explanation = form.explanation.data if any(form.explanation.data)\
                        else "No additional info provided."
                    new_report = DeletionReport(deletion_reason=form.reason.data,
                                                deletion_explanation=html2text(explanation), user=current_user)
                    db.session.add(new_report)
                    db.session.commit()
                    return redirect(url_for('generate_deletion', user_id=current_user.id))
            return render_template('config.html', config_title="Account Deletion Request",
                                   config_desc="Request to delete your account.",
                                   form=form, config_func="request_deletion", name=get_name(),
                                   background_image=get_background('website_configuration'))
    else:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))


@app.route('/handle-request/<token>')
@admin_only
def handle_request(token):
    email = request.args.get('email')
    decision = request.args.get('decision')
    try:
        confirmation = serializer.loads(token, salt='deletion_request', max_age=259200)
    except SignatureExpired:
        flash("The token is expired, please try again.")
        return redirect(url_for('home'))
    except BadTimeSignature:
        flash("Incorrect token, please try again.")
        return redirect(url_for('home'))
    else:
        requested_user = User.query.filter_by(email=email).first()
        if requested_user is not None:
            if decision == 'approved':
                request_notification(email=requested_user.email, name=requested_user.name, decision="approved")
                if current_user == requested_user:
                    logout_user()
                flash("Deletion requested approved, a notification has been sent to the user.")
                db.session.delete(requested_user)
                clean_posts()
                db.session.commit()
                return redirect(url_for('home'))
            else:
                request_notification(email=requested_user.email, name=requested_user.name, decision="rejected")
                flash("Deletion request rejected, a notification has been sent to the user.")
                requested_report = DeletionReport.query.filter_by(user=requested_user).first()
                if requested_report is not None:
                    db.session.delete(requested_report)
                db.session.commit()
                return redirect(url_for('home'))
        else:
            flash("Could not find a user with the specified ID.")
            return redirect(url_for('home'))


# ------------------ END BLOCK ------------------


@app.route('/auth', methods=['GET', 'POST'])
@admin_only
def authorization():
    form = AuthForm()
    user_id = request.args.get('user_id')
    if User.query.get(user_id) is None:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))
    if form.validate_on_submit():
        try:
            contents = get_data()
            secret_password = contents['secret_password']
        except (KeyError, TypeError, IndexError):
            flash("Authentication Password is not available. Deletion cannot be performed at this time.")
            return redirect(url_for('home'))
        if check_password_hash(secret_password, form.code.data):
            return redirect(url_for('delete_user', user_id=user_id, authorized=True))
        else:
            flash("Incorrect authorization code.")
    return render_template('delete.html', form=form, authorization=True, user_id=user_id, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/admin-auth', methods=['GET', 'POST'])
@login_required
def admin_auth():
    if get_admin_count() > 0:
        admin_redirect()
    form = AuthForm()
    remove = request.args.get('remove')
    user_id = request.args.get('user_id')
    if User.query.get(user_id) is None:
        flash("Could not find a user with the specified ID.")
        return redirect(url_for('home'))
    if form.validate_on_submit():
        contents = get_data()
        try:
            secret_password = contents['secret_password']
        except (TypeError, KeyError, IndexError):
            flash("Cannot retrieve Authentication Password, cannot set user as an administrator in this time.")
            return redirect(url_for('home'))
        if not contents:
            flash("Data File is not available, cannot retrieve authentication password."
                  " Cannot set user as an administrator in this time.")
            return redirect(url_for('home'))
        if check_password_hash(secret_password, form.code.data):
            if remove != 'True':
                return redirect(url_for('make_admin', user_id=user_id, authorized=True))
            else:
                return redirect(url_for('remove_admin', user_id=user_id, authorized=True))
        else:
            flash("Incorrect authorization code.")
    return render_template('admin-form.html', form=form, authorization=True, user_id=user_id, name=get_name(),
                           background_image=get_background('website_configuration'), category='admin',
                           remove=remove)


# ------------------ END BLOCK ------------------


# ------------------ AUTHENTICATION BLOCK ------------------

def verify_user(email, name):
    token = serializer.dumps(email, salt='email-verify')
    msg = Message('Confirmation Email', sender=os.environ.get('EMAIL', EMAIL), recipients=[email])
    link = url_for('verify_email', token=token, email=email, _external=True)
    msg.body = f"Hello {name}, please go to this link to finalize your registration.\n\n" \
               f"{link}\n\nNote: If you're unfamiliar with the source of this email, simply ignore it."
    mail.send(msg)
    flash("A confirmation email has been sent to you.")
    return redirect(url_for('home'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/register', methods=['GET', 'POST'])
@logout_required
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            password = generate_password_hash(password=form.password.data,
                                              method='pbkdf2:sha256', salt_length=8)
            new_user = User(email=form.email.data,
                            password=password, name=form.name.data)
            db.session.add(new_user)
            db.session.commit()
            verify_user(form.email.data, form.name.data)
            return redirect(url_for('home'))
        else:
            if user.confirmed_email is True:
                flash("This email already exists, please try again.")
            else:
                db.session.delete(user)
                db.session.commit()
                password = generate_password_hash(password=form.password.data,
                                                  method='pbkdf2:sha256', salt_length=8)
                new_user = User(email=form.email.data,
                                password=password, name=form.name.data)
                db.session.add(new_user)
                db.session.commit()
                verify_user(form.email.data, form.name.data)
                return redirect(url_for('home'))

            return redirect(url_for('register'))
    return render_template('register.html', form=form, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/verify/<token>')
def verify_email(token):
    email = request.args.get('email')
    try:
        confirmation = serializer.loads(token, salt='email-verify', max_age=300)
    except SignatureExpired:
        flash("The token is expired, please try again.")
        return redirect(url_for('register'))
    except BadTimeSignature:
        flash("Incorrect token, please try again.")
        return redirect(url_for('register'))
    else:
        user = User.query.filter_by(email=email).first()
        if user is not None:
            if user.confirmed_email is False:
                user.confirmed_email = True
                user.join_date = generate_date()
                db.session.commit()
                login_user(user)
                flash("You've confirmed your email successfully.")
            else:
                flash("You've already confirmed your email.")
            return redirect(url_for('home'))
        else:
            flash("This user does not exist.")
            return redirect(url_for('register'))


@app.route('/login', methods=['GET', 'POST'])
@logout_required
def login():
    form = LoginForm()
    user_name = None
    email = None
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None:
            if user.confirmed_email is True:
                if check_password_hash(user.password, form.password.data):
                    login_user(user)
                    return redirect(url_for('home'))
                else:
                    flash("Incorrect password, please try again.")
            else:
                email = user.email
                user_name = user.name
                flash("unconfirmed")
        else:
            flash("This email does not exist, please try again.")
    return render_template("login.html", form=form, email=email, user_name=user_name, name=get_name(),
                           background_image=get_background('website_configuration'))


@app.route('/validate')
def validate():
    email = request.args.get('email')
    name = request.args.get('name')
    if name is None or email is None:
        flash("Malformed validation request to server.")
        return redirect(url_for('login'))
    else:
        return verify_user(email, name)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# ------------------ END BLOCK -----------------


# ------------------ API BLOCK ------------------

@app.route('/api/generate-key', methods=['GET', 'POST'])
@login_required
def generate_key():
    if ApiKey.query.filter_by(developer=current_user).first() is None:
        form = ApiGenerate()
        if form.validate_on_submit():
            new_key = ApiKey(developer=current_user, occupation=form.occupation.data, application=form.application.data,
                             usage=html2text(form.usage.data), api_key=generate_new())
            db.session.add(new_key)
            db.session.commit()
            return redirect(url_for('user_page', user_id=current_user.id, current_mode='api'))
        return render_template('config.html', config_title="API Key Generation",
                               config_desc="Generate an API Key to use our API Service.", form=form,
                               config_func="generate_key", name=get_name(),
                               background_image=get_background('website_configuration'))
    else:
        flash("You already have an API key.")
        return redirect(url_for('user_page', user_id=current_user.id, current_mode='api'))


@app.route('/api/all-posts')
def api_all_posts():
    api_key = request.args.get('api_key')
    if api_key is not None:
        if validate_key(api_key) is True:
            try:
                requesting_user = ApiKey.query.filter_by(api_key=api_key).first()
                requesting_user.all_posts += 1
            except AttributeError:
                return abort(500)
            posts = get_posts()
            posts_dict = {posts.index(post) + 1: {"author": post.author.name,
                                                  "title": post.title,
                                                  "subtitle": post.subtitle,
                                                  "published_on": post.date,
                                                  "contents": html2text(post.body).strip(),
                                                  "img_url": post.img_url,
                                                  "comments": [
                                                      (
                                                          comment.author.name,
                                                          html2text(comment.comment).strip())
                                                      for
                                                      comment
                                                      in post.comments]}
                          for post in posts}
            db.session.commit()
            return jsonify(response=posts_dict), 200
        else:
            return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401
    else:
        return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401


@app.route('/api/random-post')
def api_random_post():
    api_key = request.args.get('api_key')
    if api_key is not None:
        if validate_key(api_key) is True:
            try:
                requesting_user = ApiKey.query.filter_by(api_key=api_key).first()
                requesting_user.random_post += 1
            except AttributeError:
                return abort(500)
            try:
                post = random.choice(get_posts())
            except IndexError:
                post_dict = {}
            else:
                post_dict = {"post": {"author": post.author.name,
                                      "title": post.title,
                                      "subtitle": post.subtitle,
                                      "published_on": post.date,
                                      "contents": html2text(post.body).strip(),
                                      "img_url": post.img_url,
                                      "comments": [(comment.author.name, html2text(comment.comment).strip()) for comment
                                                   in post.comments]
                                      }}
            db.session.commit()
            return jsonify(response=post_dict), 200
        else:
            return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401
    else:
        return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401


@app.route('/api/users')
def api_all_users():
    api_key = request.args.get('api_key')
    if api_key is not None:
        if validate_key(api_key):
            try:
                requesting_user = ApiKey.query.filter_by(api_key=api_key).first()
                requesting_user.all_users += 1
            except AttributeError:
                return abort(500)
            users = User.query.all()
            users_dict = {users.index(user) + 1: {"username": user.name,
                                                  "permissions": [
                                                      "Administrator" if user.admin is True else "Author" if user.author
                                                                                                             is True else "Registered User" if user.confirmed_email is True
                                                      else None][0],
                                                  "posts": {user.posts.index(post) + 1: get_post_dict(post) for post
                                                            in
                                                            user.posts},
                                                  "comments": {
                                                      user.comments.index(comment) + 1: {"comment": comment.comment,
                                                                                         "on_post":
                                                                                             comment.parent_post.title,
                                                                                         "post_author":
                                                                                             comment.parent_post
                                                                                                 .author.name}
                                                      for comment in user.comments}}
                          for user in users if user.confirmed_email is True}
            db.session.commit()
            return jsonify(response=users_dict)
        else:
            return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401
    else:
        return jsonify(response={"Malformed API Request": "Invalid API Key."}), 401


# @app.route('/api/copy/<int:user_id>')
# @login_required
# def copy_key(user_id):
#     if current_user.id == user_id or current_user.admin is True:
#         requested_api = ApiKey.query.filter_by(developer_id=user_id).first()
#         if requested_api is not None:
#             try:
#                 pyperclip.copy(requested_api.api_key)
#             except pyperclip.PyperclipException:
#                 flash("Could not find a copy mechanism for your OS.")
#                 return redirect(url_for('user_page', user_id=user_id, current_mode='api'))
#
#             flash("API Key copied to clipboard.")
#             return redirect(url_for('user_page', user_id=user_id, current_mode='api'))
#         else:
#             flash("Could not find an API key with the specified ID.")
#             return redirect(url_for(user_page, user_id=current_user.id))
#     else:
#         abort(403)


# ------------------ END BLOCK ------------------

# ------------------ SERVER CONFIG ------------------


if __name__ == '__main__':
    app.run(debug=True)
