use std::fs;
use std::path::PathBuf;

use artcraft_client::credentials::storyteller_avt_cookie::StorytellerAvtCookie;
use artcraft_client::credentials::storyteller_credential_set::StorytellerCredentialSet;
use artcraft_client::credentials::storyteller_session_cookie::StorytellerSessionCookie;
use log::{info, warn};
use serde_json::Value;

const CREDENTIALS_DIR: &str = "Artcraft/credentials";
const SESSION_FILE: &str = "artcraft_session.txt";
const AVT_FILE: &str = "artcraft_avt.txt";
const COOKIE_STORE: &str = "ai.artcraft.app/.cookies";

pub fn load_credentials() -> Option<StorytellerCredentialSet> {
    let home = dirs::home_dir();
    let mut cookie_paths = Vec::new();
    // Tauri stores its HTTP cookie jar in the platform cache directory.
    if let Some(cache) = dirs::cache_dir() {
        cookie_paths.push(cache.join(COOKIE_STORE));
    }
    // Preserve the legacy Windows / application-support location as a fallback.
    if let Some(data) = dirs::data_local_dir() {
        let path = data.join(COOKIE_STORE);
        if !cookie_paths.contains(&path) {
            cookie_paths.push(path);
        }
    }
    resolve_credentials(
        std::env::var("ARTCRAFT_SESSION").ok(),
        std::env::var("ARTCRAFT_AVT").ok(),
        home.map(|h| h.join(CREDENTIALS_DIR)),
        &cookie_paths,
    )
}

fn resolve_credentials(
    session_env: Option<String>,
    avt_env: Option<String>,
    credential_dir: Option<PathBuf>,
    cookie_paths: &[PathBuf],
) -> Option<StorytellerCredentialSet> {
    let clean = |value: Option<String>| value.map(|s| s.trim().to_owned()).filter(|s| !s.is_empty());
    let mut session = clean(session_env).map(StorytellerSessionCookie::new);
    let mut avt = clean(avt_env).map(StorytellerAvtCookie::new);
    if session.is_some() {
        return Some(StorytellerCredentialSet::initialize(avt, session));
    }
    if let Some(dir) = credential_dir {
        session = load_session_cookie(&dir.join(SESSION_FILE));
        if session.is_some() {
            avt = avt.or_else(|| load_avt_cookie(&dir.join(AVT_FILE)));
            return Some(StorytellerCredentialSet::initialize(avt, session));
        }
        if let Ok(content) = fs::read_to_string(dir.join("native_session.json")) {
            if let Ok(value) = serde_json::from_str::<Value>(&content) {
                session = clean(value["session"].as_str().map(str::to_owned)).map(StorytellerSessionCookie::new);
                if session.is_some() {
                    avt = avt.or_else(|| clean(value["visitor"].as_str().map(str::to_owned)).map(StorytellerAvtCookie::new));
                    return Some(StorytellerCredentialSet::initialize(avt, session));
                }
            }
        }
    }
    for path in cookie_paths {
        if let Some((Some(s), a)) = load_credentials_from_cookie_store(path) {
            return Some(StorytellerCredentialSet::initialize(avt.or(a), Some(s)));
        }
    }
    warn!("No ArtCraft session found. Sign in to ArtCraft or set ARTCRAFT_SESSION.");
    avt.map(|a| StorytellerCredentialSet::initialize(Some(a), None))
}

fn load_session_cookie(path: &PathBuf) -> Option<StorytellerSessionCookie> {
    if !path.exists() {
        return None;
    }

    match fs::read_to_string(path) {
        Ok(content) => {
            let token = content.trim();
            if token.is_empty() {
                warn!("Session file is empty: {:?}", path);
                return None;
            }
            info!("Loaded session cookie from file");
            Some(StorytellerSessionCookie::new(token.to_string()))
        }
        Err(e) => {
            warn!("Failed to read session file {:?}: {}", path, e);
            None
        }
    }
}

fn load_avt_cookie(path: &PathBuf) -> Option<StorytellerAvtCookie> {
    if !path.exists() {
        return None;
    }

    match fs::read_to_string(path) {
        Ok(content) => {
            let token = content.trim();
            if token.is_empty() {
                warn!("AVT file is empty: {:?}", path);
                return None;
            }
            info!("Loaded AVT cookie from file");
            Some(StorytellerAvtCookie::new(token.to_string()))
        }
        Err(e) => {
            warn!("Failed to read AVT file {:?}: {}", path, e);
            None
        }
    }
}

fn load_credentials_from_cookie_store(path: &PathBuf) -> Option<(Option<StorytellerSessionCookie>, Option<StorytellerAvtCookie>)> {
    if !path.exists() {
        return None;
    }

    let content = match fs::read_to_string(path) {
        Ok(c) => c,
        Err(e) => {
            warn!("Failed to read cookie store {:?}: {}", path, e);
            return None;
        }
    };

    let cookies: Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(e) => {
            warn!("Failed to parse cookie store JSON: {}", e);
            return None;
        }
    };

    let array = match cookies.as_array() {
        Some(a) => a,
        None => {
            warn!("Cookie store is not a JSON array");
            return None;
        }
    };

    let mut session = None;
    let mut avt = None;

    for cookie in array {
        let domain = cookie.get("domain").and_then(|d| {
            d.get("HostOnly").or_else(|| d.get("Suffix")).and_then(Value::as_str)
        });
        if !matches!(domain, Some("storyteller.ai" | "api.storyteller.ai" | ".storyteller.ai")) {
            continue;
        }
        if let Some(expiry) = cookie.pointer("/expires/AtUtc").and_then(Value::as_str) {
            match chrono::DateTime::parse_from_rfc3339(expiry) {
                Ok(time) if time > chrono::Utc::now() => {},
                _ => continue,
            }
        }
        if let Some(raw) = cookie.get("raw_cookie").and_then(|v| v.as_str()) {
            if raw.starts_with("session=") && session.is_none() {
                let value = raw.split(';').next().unwrap_or(raw);
                let token = value.strip_prefix("session=").unwrap_or(value);
                if !token.is_empty() {
                    info!("Loaded session cookie from Tauri cookie store");
                    session = Some(StorytellerSessionCookie::new(token.to_string()));
                }
            } else if raw.starts_with("visitor=") && avt.is_none() {
                let value = raw.split(';').next().unwrap_or(raw);
                let token = value.strip_prefix("visitor=").unwrap_or(value);
                if !token.is_empty() {
                    info!("Loaded AVT cookie from Tauri cookie store");
                    avt = Some(StorytellerAvtCookie::new(token.to_string()));
                }
            }
        }
    }

    Some((session, avt))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    struct Fixture(PathBuf);
    impl Fixture {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("artcraft-auth-{}", uuid::Uuid::new_v4()));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
        fn write(&self, name: &str, contents: &str) -> PathBuf {
            let path = self.0.join(name);
            fs::write(&path, contents).unwrap();
            path
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) { let _ = fs::remove_dir_all(&self.0); }
    }
    fn header(creds: Option<StorytellerCredentialSet>) -> String {
        creds.unwrap().maybe_as_cookie_header().unwrap()
    }

    #[test]
    fn environment_session_does_not_require_home_or_mix_accounts() {
        let f = Fixture::new();
        f.write(SESSION_FILE, "file-session");
        f.write(AVT_FILE, "file-visitor");
        let value = header(resolve_credentials(Some(" env-session \n".into()), None, Some(f.0.clone()), &[]));
        assert!(value.contains("session=env-session"));
        assert!(!value.contains("file-visitor"));
        assert!(header(resolve_credentials(Some("env".into()), None, None, &[])).contains("session=env"));
    }

    #[test]
    fn legacy_files_precede_native_session() {
        let f = Fixture::new();
        f.write(SESSION_FILE, " file-session \n");
        f.write(AVT_FILE, "file-visitor");
        f.write("native_session.json", r#"{"session":"native-session","visitor":"native-visitor"}"#);
        let value = header(resolve_credentials(None, None, Some(f.0.clone()), &[]));
        assert!(value.contains("session=file-session"));
        assert!(value.contains("visitor=file-visitor"));
        fs::remove_file(f.0.join(SESSION_FILE)).unwrap();
        let value = header(resolve_credentials(None, None, Some(f.0.clone()), &[]));
        assert!(value.contains("session=native-session"));
        assert!(value.contains("visitor=native-visitor"));
    }

    #[test]
    fn cookie_jar_rejects_other_domains_and_expired_cookies() {
        let f = Fixture::new();
        let cookies = json!([
            {"raw_cookie":"session=wrong; Path=/", "domain":{"HostOnly":"other.example"}},
            {"raw_cookie":"session=expired; Path=/", "domain":{"Suffix":"storyteller.ai"}, "expires":{"AtUtc":"2000-01-01T00:00:00Z"}},
            {"raw_cookie":"session=valid; Path=/", "domain":{"HostOnly":"api.storyteller.ai"}, "expires":{"AtUtc":"2099-01-01T00:00:00Z"}},
            {"raw_cookie":"visitor=guest; Path=/", "domain":{"Suffix":"storyteller.ai"}}
        ]);
        let path = f.write(".cookies", &cookies.to_string());
        let value = header(resolve_credentials(None, None, Some(f.0.clone()), &[path]));
        assert!(value.contains("session=valid"));
        assert!(value.contains("visitor=guest"));
        assert!(!value.contains("wrong"));
        assert!(!value.contains("expired"));
    }

    #[test]
    fn corrupt_and_missing_files_do_not_prevent_offline_startup() {
        let f = Fixture::new();
        f.write(SESSION_FILE, " \n");
        f.write("native_session.json", "bad json");
        let path = f.write(".cookies", "bad json");
        assert!(resolve_credentials(None, None, Some(f.0.clone()), &[path, f.0.join("missing")]).is_none());
    }
}
