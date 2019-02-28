from flask import (
    Blueprint,
    send_from_directory,
    current_app,
    make_response,
    request,
    render_template,
    jsonify
)
from phaunos.phaunos.models import (
    Audio,
    Tag,
    Tagset,
    Project,
    Role,
    VisualizationType,
    UserProjectRel,
    project_schema,
    tagset_schema,
#    tag_schema,
    audio_schema,
)


from flask_jwt_extended import (
    fresh_jwt_required,
    jwt_required,
    get_jwt_identity,
    get_current_user
)

from phaunos.shared import db
from phaunos.utils import build_response



phaunos_api = Blueprint('phaunos_api', __name__)


# get project (without audios and annotations) 
# all: /projects
# by id: /projects/<id> (only for project admins)

# get tagsets (with tags)
# /tagsets
# params:
#   project_id=<id> (required)

# get audios
# /audios
# params:
#   project_id=<id> (required) (only for project admins)

# get annotations
# /annotations (all if the user connected is project admin. Only those made by the user connected otherwise.)
# -filter by project: project_id=<id> (required)
#- filter by audio: audio_id=<id>
#- filter by user: user_id=<id>
#- filter by tag: tag_id=<id>

# get users
#- by id: /users/<id>
#- by project: /users?project_id=<id>





@phaunos_api.route('/')
def home():
    return 'Home'


@phaunos_api.route('/api/phaunos/projects', methods=['GET'])
#@jwt_required
def projects():
    page = request.args.get('page', 1, type=int)
    projects = Project.query.order_by(Project.name).paginate(page, 10, False)
    return project_schema.dumps(projects.items, many=True)


@phaunos_api.route('/api/phaunos/projects/<int:id>', methods=['GET'])
@jwt_required
def project_detail(id):
    user = get_current_user()
    project = Project.query.get(id)
    if not project:
        return build_response(404, f'Project with id {project_id} not found')
    if not UserProjectRel.query.filter(
            UserProjectRel.project_id==id,
            UserProjectRel.user_id==user.id,
            UserProjectRel.user_role==Role.ADMIN).first():
        return build_response(403, 'Not allowed.')
    return project_schema.dumps(project)


@phaunos_api.route('/api/phaunos/tagsets', methods=['GET'])
#@jwt_required
def tagsets():
    page = request.args.get('page', 1, type=int)
    project_id = request.args.get('project_id', None, type=int)

    # Filter by project (required)
    if not project_id:
        return build_response(422, 'Missing project_id parameter.')
    if not Project.query.get(project_id):
        return build_response(404, f'Project with id {project_id} not found')
    subquery = Tagset.query.filter(Tagset.projects.any(Project.id==project_id))

    return tagset_schema.dumps(
        subquery.paginate(page, 10, False).items,
        many=True)


@phaunos_api.route('/api/phaunos/audios', methods=['GET'])
@jwt_required
def audios():
    page = request.args.get('page', 1, type=int)
    user = get_current_user()
    project_id = request.args.get('project_id', None, type=int)

    # Filter by project (required)
    if not project_id:
        return build_response(422, 'Missing project_id parameter.')
    if not Project.query.get(project_id):
        return build_response(404, f'Project with id {project_id} not found')
    subquery = Audio.query.filter(Audio.projects.any(Project.id==project_id))

    # Check user is project admin
    if not UserProjectRel.query.filter(
            UserProjectRel.project_id==project_id,
            UserProjectRel.user_id==user.id,
            UserProjectRel.user_role==Role.ADMIN).first():
        return build_response(403, 'Not allowed.')

    return audio_schema.dumps(
        subquery.paginate(page, 10, False).items,
        many=True)


@phaunos_api.route('/api/phaunos/annotations', methods=['GET'])
@jwt_required
def annotations():
    user = get_current_user()
    project_id = request.args.get('project_id', None, type=int)
    audio_id = request.args.get('audio_id', None, type=int)
    tag_id = request.args.get('tag_id', None, type=int)

    # Filter by project (required)
    if not project_id:
        return build_response(422, 'Missing project_id parameter.')
    if not Project.query.get(project_id):
        return build_response(404, f'Project with id {project_id} not found')
    subquery = Annotation.query.filter(Annotation.project_id==project_id)
    
    # Filter by audio
    if audio_id:
        if not Audio.query.get(audio_id):
            return build_response(404, f'Audio with id {audio_id} not found')
        subquery = subquery.filter(Annotation.audio_id==audio_id)

    # Filter by tag
    if tag_id:
        if not Tag.query.get(tag_id):
            return build_response(404, f'Tag with id {tag_id} not found')
        subquery = subquery.filter(Annotation.tag_id==tag_id)

    # If the user is not project admin, only get his annotations
    if not UserProjectRel.query.filter(
            UserProjectRel.project_id==project_id,
            UserProjectRel.user_id==user.id,
            UserProjectRel.user_role==Role.ADMIN).first():
        subquery = subquery.filter(Annotation.user_id==user.id)

    return annotation_schema.dumps(
        subquery.paginate(page, 10, False).items,
        many=True)

@phaunos_api.route('/files/<path:filename>')
def uploaded(filename):
    return send_from_directory('/app/files',
            filename)
