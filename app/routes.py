from flask import render_template, flash, redirect, url_for, request
from app import app
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm
from werkzeug.urls import url_parse
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Post
from app import db
from datetime import datetime
from app.email import send_password_reset_email

@app.before_request
def before_request():
	if current_user.is_authenticated:
		current_user.last_seen = datetime.utcnow()
		db.session.commit()

@app.route('/', methods = ['GET', 'POST'])
@app.route('/index', methods = ['GET', 'POST'])
@login_required  #if the user does not login, he will not be allowed to access this page
def index():
	form = PostForm()
	if form.validate_on_submit():
		post = Post(body = form.post.data, author = current_user)
		db.session.add(post)
		db.session.commit()
		flash('Your post is now live!')
		return redirect(url_for('index'))
	# return a query for the posts that a given user wants to see
	# posts = current_user.followed_posts().all()
	# pagination function>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
	# 用法：user.followed_posts().paginate(1, 20, False).items：1是page number, 20是the number of items per page
	page = request.args.get('page', 1, type = int)
	posts = current_user.followed_posts().paginate(page, app.config['POST_PER_PAGE'], False)
	# generate next page
	next_url = url_for('index', page = posts.next_num) if posts.has_next else None
	prev_url = url_for('index', page = posts.prev_num) if posts.has_prev else None
	return render_template('index.html', title = 'HOME PAGE', form = form, posts = posts.items, next_url = next_url, prev_url = prev_url)

@app.route('/explore')
@login_required
def explore():
	page = request.args.get('page', 1, type = int)
	posts = Post.query.order_by(Post.timestamp.desc()).paginate(page, app.config['POST_PER_PAGE'], False)
	# posts = Post.query.order_by(Post.timestamp.desc()).all()
	# generate next page
	next_url = url_for('explore', page = posts.next_num) if posts.has_next else None
	prev_url = url_for('explore', page = posts.prev_num) if posts.has_prev else None
	return render_template('index.html', title = 'Explore', posts = posts.items, next_url = next_url, prev_url = prev_url)

@app.route('/login', methods = ['GET', 'POST'])
def login():
	if current_user.is_authenticated:  #check if the user is logged in or not
		return redirect(url_for('index'))
	form = LoginForm()
	if form.validate_on_submit():
		# first(): return the user object if it exists, or None if it doesn't
		# first() is executed when you only need to have one result
		user = User.query.filter_by(username = form.username.data).first()
		if user is None or not user.check_password(form.password.data):
			flash('Invalid username or password')
			return redirect(url_for('index'))
		login_user(user, remember = form.remember_me.data)
		next_page = request.args.get('next')
		# To determine if the URL is relative or absolute, 
		# I parse it with Werkzeug's url_parse() function and 
		# then check if the netloc component is set or not.
		if not next_page or url_parse(next_page).netloc != '': 
			next_page = url_for('index')
		return redirect(next_page)
	return render_template('login.html', title = 'Sign In', form = form)

@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('index'))

@app.route('/register', methods = ['GET', 'POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('index'))
	form = RegistrationForm()
	if form.validate_on_submit():
		user = User(username = form.username.data, email = form.email.data)
		user.set_password(form.password.data)
		db.session.add(user)
		db.session.commit()
		flash('Congratualations, you are now a registered user!')
		return redirect(url_for('login'))
	return render_template('register.html', title = 'Register', form = form)

@app.route('/user/<username>')  #<username>:dynamic component
@login_required
def user(username):
	# when the username does not exist in the database the function 
	# will not return and instead a 404 exception will be raised.
	user = User.query.filter_by(username = username).first_or_404()
	page = request.args.get('page', 1, type = int)
	# user.posts is the result of db.relationship() in User model.py
	posts = user.posts.order_by(Post.timestamp.desc()).paginate(page, app.config['POST_PER_PAGE'], False)
	next_url = url_for('user', username = username, page = posts.next_num) if posts.has_next else None
	prev_url = url_for('user', username = username, page = posts.prev_num) if posts.has_prev else None
	return render_template('user.html', user = user, posts = posts.items, next_url = next_url, prev_url = prev_url)

@app.route('/edit_profile', methods = ['GET', 'POST'])
@login_required
def edit_profile():
	form = EditProfileForm(current_user.username)
	if form.validate_on_submit():
		current_user.username = form.username.data
		current_user.about_me = form.about_me.data
		db.session.commit()
		flash('Your changes have been saved.')
		return redirect(url_for('edit_profile'))
	elif request.method == 'GET':
		form.username.data = current_user.username
		form.about_me.data = current_user.about_me
	return render_template('edit_profile.html', title = 'Edit Profile', form = form)

@app.route('/follow/<username>')
@login_required
def follow(username):
	user = User.query.filter_by(username = username).first()
	if user is None:
		flash('User {} not found.'.format(username))
		return redirect(url_for('index'))
	if user == current_user:
		flash('You cannot follow yourself!')
		return redirect(url_for('user', username = username))
	current_user.follow(user)
	db.session.commit()
	flash('You are following {}!'.format(username))
	return redirect(url_for('user', username = username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
	user = User.query.filter_by(username = username).first()
	if user is None:
		flash('User {} not found.'.format(username))
		return redirect(url_for('index'))
	if user == current_user:
		flash('You cannot unfollow yourself!')
		return redirect(url_for('user', username = username))
	current_user.unfollow(user)
	db.session.commit()
	flash('You are not following {}.'.format(username))
	return redirect(url_for('user', username = username))

@app.route('/reset_password_request', methods = ['GET', 'POST'])
def reset_password_request():
	if current_user.is_authenticated:
		return redirect(url_for('index'))
	form = ResetPasswordRequestForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email = form.email.data).first()
		if user:
			send_password_reset_email(user)
		flash('Check your email for the instruction to reset your password')
		return redirect(url_for('login'))
	return render_template('reset_password_request.html', title = 'Reset Password', form = form)
