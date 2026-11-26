"""PostgreSQL models (SQLAlchemy) for the catalog.

GitHub issue IDs are stored only as a link between a submission and its
project record — GitHub is not the database.
"""
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        String, Text, func)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    project_id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    website_url = Column(String(500), nullable=False)
    documentation_url = Column(String(500))
    repository_url = Column(String(500))
    creator = Column(String(200))
    category = Column(String(200))  # comma-separated slugs
    pricing_model = Column(String(50))
    open_source = Column(Boolean, default=False)
    status = Column(String(50), default="submitted")  # submitted/queued/passed/published/suspended
    quality_score = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime)
    inspections = relationship("Inspection", back_populates="project")
    pages = relationship("Page", back_populates="project")


class Inspection(Base):
    __tablename__ = "inspections"
    inspection_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    http_status = Column(Integer)
    tls_status = Column(String(50))
    dns_status = Column(String(50))
    redirect_chain = Column(Text)
    security_headers = Column(Text)
    browser_status = Column(String(50))
    console_errors = Column(Text)
    broken_links = Column(Text)
    screenshot_reference = Column(String(500))
    quality_score = Column(Integer)
    inspection_result = Column(String(50))
    project = relationship("Project", back_populates="inspections")


class Page(Base):
    __tablename__ = "pages"
    page_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    published_url = Column(String(500))
    template_version = Column(String(50))
    deployment_status = Column(String(50))
    last_deployed = Column(DateTime)
    last_verified = Column(DateTime)
    project = relationship("Project", back_populates="pages")


class TrafficEvent(Base):
    __tablename__ = "traffic"
    event_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    page_id = Column(Integer, ForeignKey("pages.page_id"))
    event_type = Column(String(50))
    referrer = Column(String(500))
    country = Column(String(10))
    device_type = Column(String(50))
    timestamp = Column(DateTime, server_default=func.now())


class AdEvent(Base):
    __tablename__ = "advertising"
    ad_event_id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.project_id"))
    placement = Column(String(100))
    network = Column(String(50), default="adsterra")
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    revenue = Column(Integer, default=0)  # minor units; never a forecast
    timestamp = Column(DateTime, server_default=func.now())


class Submission(Base):
    __tablename__ = "submissions"
    submission_id = Column(Integer, primary_key=True)
    github_issue_id = Column(Integer, unique=True)
    github_user = Column(String(200))
    submitted_data = Column(Text)
    review_status = Column(String(50), default="submitted")
    processing_log = Column(Text)
