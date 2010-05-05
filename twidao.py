from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api.labs import taskqueue
import os
import models

# login: required
class SignupPage(webapp.RequestHandler):
    def __init__(self):
        self.cur_user = users.get_current_user()
        self.user = models.Members.all().filter('user', self.cur_user).get()

    def get(self):
        if self.user :  # registered (and same Google Account)
            self.redirect('/')
        logout_url = users.create_logout_url('/')
        template_values = {'user': 'signup',
                           'signup': 'signup',
                           'logout_url': logout_url,
                           'username': 'foobar'}
        path = os.path.join(os.path.dirname(__file__), 'templates/signup.html')
        self.response.out.write(template.render(path, template_values))

    def validator(self, *args):
        return args

    def register_member(self, username, fullname, bio):
        obj = db.get(db.Key.from_path("Members", username.lower()))
        if not obj:
            obj = models.Members(key_name=username.lower(),  # unique and lower case
                                     user=self.cur_user,
                                     username=username,
                                     fullname=fullname,
                                     bio=bio,
                                     following=[],
                                     followers=[])
        else:
            # Username existed
            raise db.TransactionFailedError
        obj.put()

    def post(self):
        get_form = self.request.get
        username, fullname, bio = self.validator(get_form('username'),
                                                 get_form('fullname'),
                                                 get_form('bio'))
        try:
            db.run_in_transaction(self.register_member, username, fullname, bio)
        except db.TransactionFailedError:
            template_values = {'error':
                               "Username '%s' has been taken!" % username}
            path = os.path.join(os.path.dirname(__file__), 'templates/signup.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect('/')

class SettingPage(webapp.RequestHandler):
    def __init__(self):
        self.cur_user = users.get_current_user()
        self.user = models.Members.all().filter('user = ', self.cur_user).get()

    def get(self):
        if not self.user:  # Not registered
            self.redirect('/signup')
        else:
            logout_url = users.create_logout_url('/')
            template_values = {'user': 'setting',
                               'username': self.user.username,
                               'fullname': self.user.fullname,
                               'bio': self.user.bio,
                               'logout_url': logout_url}
            path = os.path.join(os.path.dirname(__file__), 'templates/setting.html')
            self.response.out.write(template.render(path, template_values))

    def validator(self, *args):
        return args

    def update_member(self, fullname, bio):
        u = models.Members.get_by_key_name(self.user.username)
        u.fullname, u.bio = fullname, bio
        u.put()
        #raise db.TransactionFailedError

    def upload_avator(self, avatar, size='origin'):
        a = models.Avatars(key_name=self.user.username + size,
                           content=avatar)
        a.put()

    def post(self):
        get_form = self.request.get
        fullname, bio = self.validator(get_form('fullname'), get_form('bio'))
        avatar = get_form('avatarfile')
        if avatar:
            db.run_in_transaction(self.upload_avator, avatar)
            # add task to resize-img queue
            taskqueue.Task(url='/task/avatar/resize?username=%s' % self.user.username,
                           method='GET',
                           ).add(queue_name='avatar')
        if self.user.fullname == fullname and self.user.bio == bio:
            self.redirect('/setting')
        try:
            db.run_in_transaction(self.update_member, fullname, bio)
        except db.TransactionFailedError:
            logout_url = users.create_logout_url('/')
            template_values = {'user': 'setting',
                               'username': self.user.username,
                               'fullname': self.user.fullname,
                               'bio': self.user.bio,
                               'logout_url': logout_url,
                               'error':"Oops... Try that again."}
            path = os.path.join(os.path.dirname(__file__), 'templates/setting.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect('/setting')

# Deal with request like /avatar/john/bigger
class AvatarsHandler(webapp.RequestHandler):
    def get(self, user, size='normal'):
        if size not in ('origin', 'bigger', 'normal'):
            self.redirect('/notfound')
        avatar = models.Avatars.get_by_key_name(user+size)
        if avatar:
            self.response.headers['Content-Type'] = 'image'
            self.response.out.write(avatar.content)
        # registered but not upload avatar yet
        elif models.Members.get_by_key_name(user):
            self.redirect('/static/default_avatar_%s.png' % size)
        else:
            self.redirect('/notfound')
