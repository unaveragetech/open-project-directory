"""Thin repository helpers over the SQLAlchemy models."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base, Project


def get_engine(database_url):
    return create_engine(database_url, pool_pre_ping=True)


def init_db(engine):
    Base.metadata.create_all(engine)


def get_session(database_url):
    return sessionmaker(bind=get_engine(database_url))()


def find_project_by_slug(session, slug):
    return session.query(Project).filter_by(slug=slug).first()


def find_project_by_website(session, website_url):
    return session.query(Project).filter_by(website_url=website_url).first()


def upsert_project(session, record):
    """Insert or update a project by slug; returns the Project row."""
    project = find_project_by_slug(session, record["slug"])
    if project is None:
        project = Project(**{k: v for k, v in record.items()
                             if k in Project.__table__.columns})
        session.add(project)
    else:
        for key, value in record.items():
            if key in Project.__table__.columns and key != "project_id":
                setattr(project, key, value)
    session.commit()
    return project
