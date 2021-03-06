import os
import re
import enum
from flask import current_app
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.event import listens_for
from sqlalchemy.dialects.postgresql import ENUM
from phaunos.shared import db, ma
from phaunos.user.models import User
from sqlalchemy.ext.declarative import declarative_base
from marshmallow import fields, validate, pre_load
from sqlalchemy import event

from flask_jwt_extended import (
    get_current_user,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
    verify_jwt_refresh_token_in_request,
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)


Base = declarative_base()


@enum.unique
class VisualizationType(enum.Enum):
    WAVEFORM = enum.auto()
    SPECTROGRAM = enum.auto()

@enum.unique
class Role(enum.Enum):
    PROJECTADMIN = enum.auto()
    PROJECTMEMBER = enum.auto()


audio_project_rel = db.Table(
    'audio_project_rel',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('audio_id', db.Integer, db.ForeignKey('audio.id'), primary_key=True)
)

tagset_project_rel = db.Table(
    'tagset_project_rel',
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True),
    db.Column('tagset_id', db.Integer, db.ForeignKey('tagset.id'), primary_key=True)
)

tag_tagset_rel = db.Table(
    'tag_tagset_rel',
    db.Column('tagset_id', db.Integer, db.ForeignKey('tagset.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)


class UserProjectRel(db.Model):
    __tablename__ = 'user_project_rel'
    user_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), primary_key=True)
    user_role = db.Column(ENUM(Role), nullable=False)
    user = db.relationship('User', backref=db.backref('user_project_rel', cascade='all'))
    project = db.relationship('Project', backref=db.backref('user_project_rel', cascade='all'))


# bound new method to User
def is_project_admin(self, project_id):
    return True if UserProjectRel.query.filter(
        UserProjectRel.project_id==project_id,
        UserProjectRel.user_id==self.id,
        UserProjectRel.user_role==Role.PROJECTADMIN).first() else False
User.is_project_admin = is_project_admin


class Tag(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'))
    created_by = db.relationship('User', backref=db.backref('tags', cascade='all'))
    annotations = db.relationship('Annotation',
            backref='tag',
            lazy=True,
            cascade='all')

    def __repr__(self):
        return '<name {}>'.format(self.name)

class Tagset(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'))
    created_by = db.relationship(User, backref=db.backref('tagsets', cascade='all'))
    tags = db.relationship(
        'Tag',
        secondary=tag_tagset_rel,
        lazy=True,
        backref='tagsets'
    )

    def __repr__(self):
        return '<name {}>'.format(self.name)





class Audio(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String, unique=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'))
    created_by = db.relationship(User, backref=db.backref('audios', cascade='all'))
    annotations = db.relationship(
        'Annotation',
        backref='audio',
        cascade='all',
        lazy=True
    )

    def __repr__(self):
        return '<id {}>'.format(self.path)

class Annotation(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.Float, nullable=True)
    end_time = db.Column(db.Float, nullable=True)
    tag_id = db.Column(db.Integer, db.ForeignKey(Tag.id), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    audio_id = db.Column(db.Integer, db.ForeignKey('audio.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'))
    created_by = db.relationship(User, backref=db.backref('annotations', cascade='all'))

    def __repr__(self):
        return '<id {}>'.format(self.id)



class Project(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    visualization_type = db.Column(ENUM(VisualizationType), default=VisualizationType.SPECTROGRAM, nullable=False)
    allow_regions = db.Column(db.Boolean, nullable=False)
    audiolist_filename = db.Column(db.String, nullable=False)
    taglist_filename = db.Column(db.String, nullable=False)
    min_annotations_per_file = db.Column(db.Integer, default=1, nullable=False)
    members_only = db.Column(db.Boolean, default=False, nullable=False)
#    created_by_id = db.Column(db.Integer, db.ForeignKey('phaunos_user.id'))
#    created_by = db.relationship(User, backref=db.backref('projects', cascade='all'))
    tagsets = db.relationship('Tagset',
            secondary=tagset_project_rel,
            lazy=True,
            backref=db.backref('projects', lazy=True))
    audios = db.relationship('Audio',
            secondary=audio_project_rel,
            lazy=True,
            backref=db.backref('projects', lazy=True))
    annotations = db.relationship(
        'Annotation',
        lazy=True,
        cascade='all',
        backref='project'
    )

    
    @property
    def n_annotations(self):
        return len(self.annotations)

    @property
    def percentage_of_completion(self):

        n_annotations = 0
        
        for audio_id in [audio.id for audio in self.audios]:
            n_annotations += min(
                len(db.session.query(Annotation.created_by_id).filter(Annotation.project_id==self.id).filter(Annotation.audio_id==audio_id).distinct().all()),
                self.min_annotations_per_file
            )

        return n_annotations // (self.min_annotations_per_file * len(self.audios)) * 100

#    @property
#    def is_completed(self):
#        if (self.n_annotations_per_file and
#                self.annotations.count() >= self.audios.count() * self.n_annotations_per_file):
#            return True
#        return False

    def __repr__(self):
        return '<name {}>'.format(self.name)


class EnumField(fields.Field):

    def __init__(self, enumtype, *args, **kwargs):
        super(EnumField, self).__init__(*args, **kwargs)
        self._enumtype = enumtype

    def _serialize(self, value, attr, obj, **kwargs):
        return value.name

    def _deserialize(self, value, attr, data, **kwargs):
        return self._enumtype[value]


class ProjectSchema(ma.ModelSchema):
    visualization_type = EnumField(VisualizationType)
    class Meta:
        model = Project
        exclude = (
            'tagsets',
            'audios',
            'annotations',
            'user_project_rel')
project_schema = ProjectSchema()


class TagSchema(ma.ModelSchema):
    class Meta:
        model = Tag
        exclude = ('annotations', 'tagsets')
#tag_schema = TagSchema()


class TagsetSchema(ma.ModelSchema):
    class Meta:
        model = Tagset
        exclude = ('projects',)
    tags = ma.Nested(TagSchema, many=True)
tagset_schema = TagsetSchema()


class AudioSchema(ma.ModelSchema):
    class Meta:
        model = Audio
        exclude = ('projects', 'annotations')

audio_schema = AudioSchema()


class AnnotationSchema(ma.ModelSchema):
    class Meta:
        model = Annotation

annotation_schema = AnnotationSchema()


class UserSchema(ma.Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(
        required=True,
        validate=[validate.Length(min=4, max=20)],
    )
    email = fields.Str(
        required=True,
        validate=validate.Email(error='Not a valid email address'),
    )
    password = fields.Str(
        required=True,
        validate=[validate.Length(min=6, max=36)],
        load_only=True,
    )

    # Clean up data
    @pre_load
    def process_input(self, data):
        data['email'] = data['email'].lower().strip()
        return data

    # We add a post_dump hook to add an envelope to responses
#    @post_dump(pass_many=True)
#    def wrap(self, data, many):
#        key = 'users' if many else 'user'
#        return {
#            key: data,
#        }


user_schema = UserSchema()



###################
# Event listeners #
###################

@event.listens_for(db.session, 'transient_to_pending')
def get_audiolist_from_file(session, instance):
    if isinstance(instance, Project):
        with open(os.path.join(
                current_app.config['FILE_FOLDER'],
                instance.audiolist_filename), 'r') as audiolist_file:
            for line in audiolist_file:
                _path = line.strip()
                audio = Audio.query.filter(Audio.path==_path).first()
                if not audio:
                    audio = Audio()
                    audio.path = _path 
                if not audio in instance.audios:
                    instance.audios.append(audio) 


@event.listens_for(db.session, 'transient_to_pending')
def get_taglist_from_file(session, instance):    
    if isinstance(instance, Project):
        with open(os.path.join(
                current_app.config['FILE_FOLDER'],
                instance.taglist_filename), 'r') as taglist_file:
            for line in taglist_file:
                line = line.strip()
                tagset_name, tag_name = line.split(',')
                tagset = Tagset.query.filter(Tagset.name==tagset_name).first()
                if not tagset:
                    tagset = Tagset()
                    tagset.name = tagset_name
                    db.session.flush(tagset)
                tag = Tag.query.filter(Tag.name==tag_name).filter(Tag.tagsets.any(Tagset.name==tagset_name)).first()
                if not tag:
                    tag = Tag()
                    tag.name = tag_name
                    tagset.tags.append(tag)
                if not tagset in instance.tagsets:
                    instance.tagsets.append(tagset)



#@listens_for(Project, 'after_delete')
#def del_file(mapper, connection, target):
#    if target.audios_filename:
#        try:
#            os.remove(os.path.join(app.config['UPLOAD_DIR'], 'audios', target.audios_filename))
#        except OSError:
#            # Don't care if was not deleted because it does not exist
#            pass
#    if target.annotations_filename:
#        try:
#            os.remove(os.path.join(app.config['UPLOAD_DIR'], 'annotations', target.annotations_filename))
#        except OSError:
#            # Don't care if was not deleted because it does not exist
#            pass
#
#



##############
# Validation #
##############

VALID_AUDIO_EXT = ['wav', 'mp3']

def validate_audiolist(instream):
    error = ''
    is_empty = True
    for i, line in enumerate(instream):
        is_empty = False
        line = line.decode().strip()
        if not re.match(r'.+({})$'.format('|'.join(VALID_AUDIO_EXT)), line):
            error = 'Wrong audio extension in line {}: {}. Only {} are accepted.'.format(i+1, line, ','.join(VALID_AUDIO_EXT))
            break
    instream.seek(0)
    if is_empty:
        error = 'Audio list file is empty.'
    return error


def validate_taglist(instream):
    error = ''
    is_empty = True
    for i, line in enumerate(instream):
        is_empty = False
        line = line.decode().strip()
        if not re.match(r'^[a-zA-Z0-9_\s\?]+,[a-zA-Z0-9_\s]+$', line):
            error = 'Wrong format in line {}: {}. Must be <tagsetname>,<tagname>.'.format(i+1, line)
            break
    instream.seek(0)
    if is_empty:
        error = 'Tag list file is empty.'
    return error
