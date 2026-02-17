import pickle
import streamlit as st
import requests
import pandas as pd
import faiss
import numpy as np
import concurrent.futures
import json
import os
import ast
from datetime import datetime
from streamlit_oauth import OAuth2Component

# --- PAGE CONFIG ---
st.set_page_config(page_title="Movie Recommender System", page_icon="🎬", layout="wide")

# --- OAUTH SETUP ---
try:
    CLIENT_ID = st.secrets["google"]["client_id"]
    CLIENT_SECRET = st.secrets["google"]["client_secret"]
    REDIRECT_URI = st.secrets["google"]["redirect_uri"]
except KeyError:
    st.error("Missing Google OAuth secrets in .streamlit/secrets.toml")
    st.stop()

AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_TOKEN_URL = "https://oauth2.googleapis.com/revoke"

# --- FILES MANAGEMENT ---
HISTORY_FILE = "history.json"
SESSION_FILE = "session.json"


def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_to_history(user_email, input_movies, selected_genres, recommended_movies):
    history = load_history()
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_email,
        "inputs": input_movies,
        "genres": selected_genres,
        "recommendations": [m['title'] for m in recommended_movies]
    }
    history.insert(0, new_entry)
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)


# --- LOGIN PERSISTENCE ---
def save_session(token, email):
    with open(SESSION_FILE, "w") as f:
        json.dump({"token": token, "email": email}, f)


def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None


def clear_session():
    if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)


# --- DATA LOADING (GLOBAL) ---
@st.cache_resource
def load_data():
    try:
        # Load Movies
        movies_df = pd.DataFrame(pickle.load(open('movies_dict.pkl', 'rb')))

        # FIX: Clean Genres Format
        def parse_genres(x):
            try:
                if isinstance(x, list): return [i['name'] for i in x]
                if isinstance(x, str):
                    if "name" in x: return [i['name'] for i in ast.literal_eval(x)]
                    return [x]
                return []
            except:
                return []

        if 'genres' in movies_df.columns:
            movies_df['genres'] = movies_df['genres'].apply(parse_genres)
        else:
            movies_df['genres'] = [[] for _ in range(len(movies_df))]

        vectors = pickle.load(open('vectors.pkl', 'rb'))
        index = faiss.read_index("movie_index.faiss")
        return movies_df, vectors, index
    except Exception as e:
        st.error(f"Critical Error loading data: {e}")
        return None, None, None


# --- CRITICAL FIX: LOAD VARIABLES GLOBALLY ---
# This ensures 'movies' is available everywhere
movies, vectors, index = load_data()


# --- API HELPER ---
def fetch_movie_details(movie_id):
    TMDB_API_KEY = "3a9c8777be4fc606e8cf6b00aff9a86e"
    default_data = {
        "summary": "Plot summary unavailable.",
        "rating": "N/A",
        "poster": "https://via.placeholder.com/500x750?text=No+Poster"
    }
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
        response = requests.get(url, timeout=1.5)
        if response.status_code != 200: return default_data
        data = response.json()
        poster_path = data.get("poster_path")
        full_poster = "https://image.tmdb.org/t/p/w500" + poster_path if poster_path else default_data['poster']
        return {
            "summary": data.get("overview", ""),
            "rating": round(data.get("vote_average", 0), 1),
            "poster": full_poster
        }
    except:
        return default_data


# --- RECOMMENDATION LOGIC (SMART FALLBACK) ---
def get_recommendations_hybrid(selected_movies, selected_genres):
    if not selected_movies: return []

    # 1. Get Indices
    selected_indices = []
    for m in selected_movies:
        matches = movies[movies['title'] == m].index
        if not matches.empty: selected_indices.append(matches[0])

    if not selected_indices: return []

    # 2. Average Vector
    user_vector = np.mean(vectors[selected_indices], axis=0).reshape(1, -1).astype('float32')

    # 3. Search (Fetch extra results to allow filtering)
    distances, indices = index.search(user_vector, k=100)

    recommendations = []
    genre_matches = []
    fallback_matches = []

    # 4. Filter Logic
    for i in indices[0]:
        if i in selected_indices: continue  # Skip own movies

        movie_row = movies.iloc[i]
        movie_genres = movie_row.genres

        # Check strict genre match
        if selected_genres:
            overlap = any(g in selected_genres for g in movie_genres)
            if overlap:
                genre_matches.append(i)
            else:
                fallback_matches.append(i)  # Keep as backup
        else:
            genre_matches.append(i)  # No genre filter = everything matches

    # 5. Smart Selection
    # If we found enough genre matches, use them.
    # If NOT, fill the rest with fallback matches so the list isn't empty.
    final_indices = genre_matches[:5]
    if len(final_indices) < 5:
        needed = 5 - len(final_indices)
        final_indices.extend(fallback_matches[:needed])

    # 6. Fetch Details
    def fetch_worker(idx):
        mid = movies.iloc[idx].movie_id
        title = movies.iloc[idx].title
        details = fetch_movie_details(mid)
        details['title'] = title
        return details

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(fetch_worker, final_indices)
        for res in results:
            if res: recommendations.append(res)

    return recommendations


# --- MAIN APP UI ---
def main_app(user_email):
    st.sidebar.title(f"👤 {user_email}")
    page = st.sidebar.radio("Navigate", ["Home", "My History"])

    if st.sidebar.button("Logout"):
        del st.session_state["token"]
        clear_session()
        st.rerun()

    if page == "Home":
        st.title("🎬 Smart Movie Recommender")
        st.write("Tell us what you like, and we'll build a custom playlist for you.")

        col1, col2 = st.columns(2)

        all_genres = ["Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama", "Family",
                      "Fantasy", "History", "Horror", "Music", "Mystery", "Romance", "Science Fiction", "Thriller",
                      "War", "Western"]

        with col1:
            st.subheader("1. Pick Genres (Optional)")
            selected_genres = st.multiselect("Filter by Genre", all_genres)

        with col2:
            st.subheader("2. Pick Movies")
            if movies is not None:
                # Get the titles and sort them alphabetically
                movie_titles = sorted(movies['title'].values)

                # Pass the sorted list to the widget
                selected_movies = st.multiselect("Select at least 3 movies", movie_titles)
            else:
                st.error("Movie data not loaded.")
                selected_movies = []

        if st.button("Generate Recommendations", type="primary"):
            if len(selected_movies) < 1:
                st.warning("⚠️ Please select at least 1 movie.")
            else:
                with st.spinner("Analyzing..."):
                    recs = get_recommendations_hybrid(selected_movies, selected_genres)

                    if recs:
                        st.success(f"Found {len(recs)} recommendations for you:")
                        save_to_history(user_email, selected_movies, selected_genres, recs)

                        cols = st.columns(5)
                        for i, movie in enumerate(recs[:5]):
                            with cols[i]:
                                st.image(movie['poster'], use_container_width=True)
                                st.caption(f"**{movie['title']}**")
                                st.write(f"⭐ {movie['rating']}")
                    else:
                        st.error("No matches found.")

    elif page == "My History":
        st.title("📜 History")
        history = load_history()
        user_history = [h for h in history if h.get('user') == user_email]

        if not user_history:
            st.info("No history found.")
        else:
            for item in user_history:
                with st.expander(f"📅 {item['timestamp']} - {len(item['inputs'])} movies selected"):
                    st.write(f"**Inputs:** {', '.join(item['inputs'])}")
                    st.write(f"**Genres:** {', '.join(item['genres'])}")
                    st.divider()
                    st.write("**Results:** " + ", ".join(item['recommendations']))


# --- LOGIN FLOW ---
if "token" not in st.session_state:
    saved_session = load_session()

    if saved_session:
        st.session_state["token"] = saved_session["token"]
        st.session_state["user_email"] = saved_session["email"]
        st.rerun()
    else:
        st.title("Login Required")
        oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZATION_URL, TOKEN_URL, TOKEN_URL, REVOKE_TOKEN_URL)
        result = oauth2.authorize_button(
            name="Continue with Google",
            icon="https://www.google.com.tw/favicon.ico",
            redirect_uri=REDIRECT_URI,
            scope="email",
            key="google",
        )
        if result and result.get("token"):
            st.session_state["token"] = result.get("token")
            st.session_state["user_email"] = result.get("user_email", "User")
            save_session(result.get("token"), st.session_state["user_email"])
            st.rerun()
else:
    main_app(st.session_state.get("user_email", "User"))