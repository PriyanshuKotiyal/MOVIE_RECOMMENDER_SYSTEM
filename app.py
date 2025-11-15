import pickle
import streamlit as st
import requests
import pandas as pd
import time
import urllib3

# Disable the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---
# 1. PROXY SETUP
# ---
# This is the proxy your network requires
# NOTE: This proxy is for your local network and will not be used by Render.
# Render has its own direct connection to the internet.
proxies = {
    "http": "http://edcguest:edcguest@172.31.102.29:3128",
    "https": "http://edcguest:edcguest@172.31.102.29:3128"
}

# ---
# 2. TMDB API KEY
# ---
TMDB_API_KEY = "3a9c8777be4fc606e8cf6b00aff9a86e"


# ---
# 3. FETCH_POSTER FUNCTION (using TMDB)
# ---
def fetch_poster(movie_id):
    """
    Fetches a movie poster from the TMDB API using the movie ID.
    """
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"

    try:
        # When running locally, we use the proxy.
        # When deployed on Render, this 'proxies' variable won't be used.
        # We will use Render's "Environment Variables" to run without a proxy.
        # For now, this is correct for your local machine:
        response = requests.get(url, proxies=proxies, verify=False, timeout=5)
        response.raise_for_status()  # Check for HTTP errors

        data = response.json()

        if "poster_path" in data and data["poster_path"]:
            return "https://image.tmdb.org/t/p/w500" + data['poster_path']
        else:
            # Don't show an error for missing poster, just return empty
            return ""

    except Exception as e:
        # Don't show error in the app, just print to log and return empty
        print(f"Error fetching poster for {movie_id}: {e}")
        return ""


# ---
# 4. RECOMMEND FUNCTION (with time.sleep)
# ---
def recommend(movie):
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])

    recommended_movie_names = []
    recommended_movie_posters = []

    for i in distances[1:6]:
        # Get the TMDB movie_id and title from the DataFrame
        movie_id = movies.iloc[i[0]].movie_id
        movie_title = movies.iloc[i[0]].title

        # Pass the movie_id to fetch_poster
        recommended_movie_posters.append(fetch_poster(movie_id))
        recommended_movie_names.append(movie_title)

        # Add a small delay to avoid rate-limiting by the proxy/API
        time.sleep(0.3)

    return recommended_movie_names, recommended_movie_posters


# ---
# 5. STREAMLIT UI (with correct indentation)
# ---
st.header('🎬 Movie Recommender System Using Machine Learning')

movies_dict = pickle.load(open('movies_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

movie_list = movies['title'].values
selected_movie = st.selectbox("Type or select a movie from the dropdown", movie_list)

# This block is now correctly indented
if st.button('Show Recommendation'):
    recommended_movie_names, recommended_movie_posters = recommend(selected_movie)
    cols = st.columns(5)
    for i in range(5):
        with cols[i]:
            st.text(recommended_movie_names[i])
            if recommended_movie_posters[i]:
                st.image(recommended_movie_posters[i])