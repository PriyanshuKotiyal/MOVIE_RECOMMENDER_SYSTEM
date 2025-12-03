import pickle
import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
TMDB_API_KEY = "3a9c8777be4fc606e8cf6b00aff9a86e"


# --- 1. DATA LOADING ---
@st.cache_resource
def load_data():
    try:
        movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
        movies = pd.DataFrame(movies_dict)
        similarity = pickle.load(open('similarity.pkl', 'rb'))
        return movies, similarity
    except FileNotFoundError:
        st.error("Error: Pickle files not found. Please make sure .pkl files are in the folder.")
        return None, None


movies, similarity = load_data()


# --- 2. API FUNCTION WITH IMAGES & PROXY ---
def fetch_movie_details(movie_id):
    details = {
        "poster": "https://via.placeholder.com/500x750?text=No+Poster",  # Fallback image
        "summary": "No summary available.",
        "rating": "N/A",
        "cast": []  # List of dicts: {'name': 'Name', 'photo': 'url'}
    }

    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US&append_to_response=credits"

        # LOGIC: Use proxy if enabled, otherwise direct connection
        if USE_PROXY:
            response = requests.get(url, timeout=5, verify=False)
        else:
            response = requests.get(url, timeout=5)

        response.raise_for_status()
        data = response.json()

        # 1. Get Poster
        if data.get('poster_path'):
            details['poster'] = "https://image.tmdb.org/t/p/w500" + data['poster_path']

        # 2. Get Summary & Rating
        details["summary"] = data.get("overview", "No summary available.")
        details["rating"] = data.get("vote_average", "N/A")

        # 3. Get Cast (Name + Photo)
        if "credits" in data and "cast" in data["credits"]:
            for actor in data["credits"]["cast"][:5]:  # Top 5 actors
                actor_data = {'name': actor['name'], 'photo': None}

                # Check if actor has a photo
                if actor.get('profile_path'):
                    actor_data['photo'] = "https://image.tmdb.org/t/p/w185" + actor['profile_path']
                else:
                    # Fallback icon for actors with no photo
                    actor_data['photo'] = "https://via.placeholder.com/185x278?text=No+Img"

                details['cast'].append(actor_data)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for ID {movie_id}: {e}")

    return details


# --- 3. RECOMMEND FUNCTION ---
def recommend(movie):
    try:
        index = movies[movies['title'] == movie].index[0]
        distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

        recommended_data = []

        for i in distances[1:6]:
            movie_id = movies.iloc[i[0]].movie_id
            title = movies.iloc[i[0]].title

            # Fetch all rich data (Poster, cast photos, etc.)
            details = fetch_movie_details(movie_id)
            details['title'] = title  # Add title to the details dict

            recommended_data.append(details)

        return recommended_data

    except IndexError:
        st.error("Movie not found in database.")
        return []


# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="Movie Recommender", page_icon="🎬", layout="wide")

st.title('🎬 Movie Recommender System')

if movies is not None:
    movie_list = movies['title'].values
    selected_movie = st.selectbox("Type or select a movie", movie_list)

    if st.button('Show Recommendation'):
        with st.spinner('Fetching recommendations...'):
            recommendations = recommend(selected_movie)

        if recommendations:
            st.subheader(f"Because you watched {selected_movie}:")

            # Display each movie in a separate container
            for movie in recommendations:
                with st.container():
                    # Create two columns: Poster (Left) and Details (Right)
                    col1, col2 = st.columns([1, 3])

                    with col1:
                        st.image(movie['poster'], width=200)

                    with col2:
                        st.subheader(movie['title'])
                        st.markdown(f"**Rating:** ⭐ {movie['rating']:.1f}/10")
                        st.write(movie['summary'])

                        # Cast Section: Horizontal layout for actors
                        st.markdown("**Cast:**")
                        cast_cols = st.columns(5)  # 5 columns for 5 actors
                        for i, actor in enumerate(movie['cast']):
                            with cast_cols[i]:
                                st.image(actor['photo'], width=100)
                                st.caption(actor['name'])

                    st.divider()  # Add a line between movies