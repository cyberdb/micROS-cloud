#coding:utf-8
from flask import Flask, request, redirect, url_for
from flask import render_template, flash, redirect, session, url_for, request, g
from flask_login import login_user, logout_user, current_user, login_required
from flask import jsonify,send_from_directory,abort
from app import app, db, lm
from app.models import User
from app.dockerops import *
from app.supervise_containers import *
import os, sys

reload(sys)
sys.setdefaultencoding('utf-8')

port = 9090
downloadFileName = None
@lm.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@app.before_request
def before_request():
    g.user = current_user
    
@app.route('/')
@app.route('/index')
@login_required
def index():
    posts = [{ 'body': 'Welcome to Robot Cloud!' }]
    return render_template('index.html',posts=posts)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    from forms import SignupForm
   
    form = SignupForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user is not None:
            form.email.errors.append("The Email address is already taken.")
            return render_template('signup.html', form=form)

        newuser = User(form.firstname.data,form.lastname.data,form.email.data,form.password.data)
        db.session.add(newuser)
        db.session.commit()

        session['email'] = newuser.email
        return redirect(url_for('login'))
   
    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('index'))

    from app.forms import LoginForm

    form = LoginForm()
    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            session['email'] = form.email.data
            login_user(user,remember=session['remember_me'])
            return redirect(url_for('index'))
        else:
            return render_template('login.html',form=form,failed_auth=True)
             
    return render_template('login.html',form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    from app.forms import UploadForm
    
    form = UploadForm()
    if form.validate_on_submit():
        action_error_msg = None
        param_do = form.do_action.data
        
        if (param_do == 'upload'):
            action_msg = uploadFile(form.ros_file.data, form.manifest_file.data, form.comments.data)
        action_list = action_msg.split(";")
        action_error_msg = action_list[0]
        proxy_name = action_list[1]
        succeed = (action_error_msg == "None")
        if succeed == True:
            return render_template('download.html',download_url = "http://127.0.0.1:5002/download/"+proxy_name)
        else:
            return render_template('upload.html',form=form, action_error_msg = action_error_msg, succeed = succeed)   
         
    return render_template('upload.html',form=form, action_error_msg = None, succeed = False)

@app.route('/download/<string:proxy_name>', methods=['GET'])
def download(proxy_name):
    from app.forms import UploadForm
    
    form = UploadForm()
    proxy_name_zip = proxy_name + ".zip"
    path1 = app.root_path+'/download'
    path2 =  os.path.join(path1, proxy_name_zip)
    if os.path.exists(path2):
        return send_from_directory(path1,proxy_name_zip,as_attachment=True)
    action_error_msg = downloadFileBuild(proxy_name)
    if None == action_error_msg:
        return send_from_directory(path1,proxy_name_zip,as_attachment=True)
    else:
        return render_template('upload.html',form=form, action_error_msg = action_error_msg, succeed = False)


@app.route('/images', methods=['GET'])
def images():
    from app import db, models 
        
    images = models.Image.query.all()
    result = []
    part_line = {'imagename':'default','uploadname':'default','uploaduser':'default','comments':'default'}
    #part_line = {}
    for i in images:
        part_line['imagename'] = i.imagename
        part_line['uploadname'] = i.uploadname
        part_line['uploaduser'] = i.uploaduser
        part_line['comments'] = i.comments
        result.append(part_line)
        part_line = {}
    return render_template('images.html',imagetables = result)
  
@app.route('/detailed/<string:image_name>', methods=['GET'])
def detailed(image_name):
    from app import db, models 
    
    image = models.Image.query.filter_by(imagename = image_name).first()
    return render_template('detailed.html',imagename = image.imagename, uploadname = image.uploadname, uploaduser = image.uploaduser, uploadtime = image.uploadtime, subscribed_topics = StringToList(image.subscribed_topics), published_topics = StringToList(image.published_topics), advertised_services = StringToList(image.advertised_services), advertised_actions = StringToList(image.advertised_actions), comments = image.comments)

@app.route('/delete/<string:image_name>', methods=['GET'])
def delete(image_name):
    from app import db, models 
    
    image = models.Image.query.filter_by(imagename = image_name).first()
    db.session.delete(image)
    db.session.commit()
    return render_template('delete.html', imagename = image_name)


@app.route('/getinstance/<string:image_name>', methods=['GET'])
def get_instance(image_name):
    
    import socket
    
    hostname = socket.getfqdn(socket.gethostname(  ))
    ipaddr = socket.gethostbyname(hostname)
    return 'ws://' + ipaddr + ':' + str(getContainerPort(image_name, ''))
    
      
@app.route('/ping/<string:container_id>', methods=['GET'])
def ping(container_id):
    
    
    from app import db, models
    from models import Container
    finding = Container.query.filter_by(containerid=container_id).first()
    if finding is not None:
        u = models.Container(containerid=container_id, createdtime=str(time.time()))
        db.session.add(u) 
        db.session.commit() 
        db.session.delete(finding)
        db.session.commit()
    else:
        u = models.Container(containerid=container_id, createdtime=str(time.time()))
        db.session.add(u) 
        db.session.commit() 
    
    return "There are existing containers."
        
