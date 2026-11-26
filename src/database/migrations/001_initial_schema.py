"""Initial schema migration (001).

Creates: projects, inspections, pages, traffic, advertising, submissions.
Apply with your migration runner of choice (e.g. Alembic); this file
documents the DDL so the schema is reproducible without one.
"""
DDL = """
CREATE TABLE IF NOT EXISTS projects (
  project_id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  slug VARCHAR(200) UNIQUE NOT NULL,
  description TEXT NOT NULL,
  website_url VARCHAR(500) NOT NULL,
  documentation_url VARCHAR(500),
  repository_url VARCHAR(500),
  creator VARCHAR(200),
  category VARCHAR(200),
  pricing_model VARCHAR(50),
  open_source BOOLEAN DEFAULT FALSE,
  status VARCHAR(50) DEFAULT 'submitted',
  quality_score INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  published_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS inspections (
  inspection_id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(project_id),
  timestamp TIMESTAMPTZ DEFAULT now(),
  http_status INTEGER,
  tls_status VARCHAR(50),
  dns_status VARCHAR(50),
  redirect_chain TEXT,
  security_headers TEXT,
  browser_status VARCHAR(50),
  console_errors TEXT,
  broken_links TEXT,
  screenshot_reference VARCHAR(500),
  quality_score INTEGER,
  inspection_result VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS pages (
  page_id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(project_id),
  published_url VARCHAR(500),
  template_version VARCHAR(50),
  deployment_status VARCHAR(50),
  last_deployed TIMESTAMPTZ,
  last_verified TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS traffic (
  event_id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(project_id),
  page_id INTEGER REFERENCES pages(page_id),
  event_type VARCHAR(50),
  referrer VARCHAR(500),
  country VARCHAR(10),
  device_type VARCHAR(50),
  timestamp TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS advertising (
  ad_event_id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(project_id),
  placement VARCHAR(100),
  network VARCHAR(50) DEFAULT 'adsterra',
  impression_count INTEGER DEFAULT 0,
  click_count INTEGER DEFAULT 0,
  revenue INTEGER DEFAULT 0,
  timestamp TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS submissions (
  submission_id SERIAL PRIMARY KEY,
  github_issue_id INTEGER UNIQUE,
  github_user VARCHAR(200),
  submitted_data TEXT,
  review_status VARCHAR(50) DEFAULT 'submitted',
  processing_log TEXT
);
"""


def upgrade(conn):
    conn.execute(DDL)
