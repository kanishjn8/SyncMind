CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255) NULL,
  locale VARCHAR(16) NULL,
  country VARCHAR(128) NULL,
  region VARCHAR(128) NULL,
  city VARCHAR(128) NULL,
  country_code VARCHAR(8) NULL,
  location_updated_at DATETIME NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_tokens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  platform VARCHAR(50) NOT NULL,
  access_token VARCHAR(1024) NOT NULL,
  refresh_token VARCHAR(1024) NULL,
  expires_in INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_user_platform (user_id, platform),
  INDEX idx_access_token (access_token(255)),
  CONSTRAINT fk_user_tokens_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS youtube_user_data (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  channel_name VARCHAR(255) NULL,
  subscribers INT DEFAULT 0,
  time_spent INT DEFAULT 0,
  recent_liked_video TEXT NULL,
  last_updated DATETIME NULL,
  UNIQUE KEY uniq_youtube_user (user_id),
  CONSTRAINT fk_youtube_user_data_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS github_user_data (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  public_repos INT DEFAULT 0,
  total_stars INT DEFAULT 0,
  contributions INT DEFAULT 0,
  last_updated DATETIME NULL,
  UNIQUE KEY uniq_github_user (user_id),
  CONSTRAINT fk_github_user_data_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS youtube_recommendations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT NULL,
  published_at DATETIME NULL,
  duration VARCHAR(100) NULL,
  views BIGINT DEFAULT 0,
  channel_name VARCHAR(255) NULL,
  url TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_youtube_reco_user (user_id),
  CONSTRAINT fk_youtube_recommendations_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS github_recommendations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  repo_name VARCHAR(255) NOT NULL,
  url TEXT NULL,
  description TEXT NULL,
  stars INT DEFAULT 0,
  forks INT DEFAULT 0,
  language VARCHAR(100) NULL,
  owner VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_github_reco_user (user_id),
  CONSTRAINT fk_github_recommendations_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS coursera_recommendations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  course_title VARCHAR(500) NOT NULL,
  provider VARCHAR(255) NULL,
  enrolled VARCHAR(100) NULL,
  rating VARCHAR(50) NULL,
  fetched_at DATETIME NULL,
  url TEXT NULL,
  info TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_coursera_reco_user (user_id),
  CONSTRAINT fk_coursera_recommendations_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_recommendations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  job_id VARCHAR(512) NULL,
  title VARCHAR(500) NOT NULL,
  company_name VARCHAR(255) NULL,
  location VARCHAR(255) NULL,
  via VARCHAR(255) NULL,
  description TEXT NULL,
  thumbnail TEXT NULL,
  share_link TEXT NULL,
  apply_link TEXT NULL,
  posted_at VARCHAR(64) NULL,
  schedule_type VARCHAR(64) NULL,
  query_used VARCHAR(255) NULL,
  location_used VARCHAR(255) NULL,
  fetched_at DATETIME NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_jobs_user (user_id),
  CONSTRAINT fk_job_recommendations_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
);
