import pandas as pd
import pickle
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
import os

print("⏳ Loading MovieLens data...")

# 1. Load the Data
# Ensure you have 'ratings.csv' and 'links.csv' in the same folder
try:
    ratings = pd.read_csv('ratings.csv')  # User ratings (userId, movieId, rating, timestamp)
    links = pd.read_csv('links.csv')      # ID Mapping (movieId, imdbId, tmdbId)
except FileNotFoundError:
    print("❌ Error: 'ratings.csv' or 'links.csv' not found.")
    print("   Please download 'ml-latest-small.zip' from https://grouplens.org/datasets/movielens/latest/")
    print("   and extract those two files into this folder.")
    exit()

print("⚙️ Processing data...")

# 2. Merge Ratings with Links (to get tmdbId)
# We merge on 'movieId' (MovieLens ID) to get the 'tmdbId' which our main app uses.
data = ratings.merge(links, on='movieId')

# Drop rows where tmdbId is missing (some older movies might not have one)
data = data.dropna(subset=['tmdbId'])
data['tmdbId'] = data['tmdbId'].astype(int)

# 3. Filter Data (Optimization)
# To keep the file size small and recommendations accurate, we filter out noise.
# We only keep movies that have been rated by at least 50 users.
movie_counts = data.groupby('tmdbId')['rating'].count()
valid_movies = movie_counts[movie_counts >= 50].index

# Filter the main dataframe to include only these valid movies
final_data = data[data['tmdbId'].isin(valid_movies)]

# We also filter for active users (users who rated at least 50 movies)
user_counts = final_data.groupby('userId')['rating'].count()
valid_users = user_counts[user_counts >= 50].index
final_data = final_data[final_data['userId'].isin(valid_users)]

print(f"   - Original ratings: {len(data)}")
print(f"   - Filtered ratings: {len(final_data)}")
print(f"   - Unique movies: {final_data['tmdbId'].nunique()}")
print(f"   - Unique users: {final_data['userId'].nunique()}")

# 4. Create the User-Item Matrix (Pivot Table)
# Rows = Movies (tmdbId)
# Columns = Users (userId)
# Values = Ratings
print("📊 Creating pivot table...")
pivot_table = final_data.pivot_table(index='tmdbId', columns='userId', values='rating').fillna(0)

# 5. Convert to Sparse Matrix (Compressed)
# A full matrix is mostly zeros (users haven't seen most movies).
# A sparse matrix compresses this to save huge amounts of memory.
collab_matrix = csr_matrix(pivot_table.values)

# 6. Train the KNN Model (Item-Item Collaborative Filtering)
# We use Cosine Similarity to find movies with similar rating patterns.
print("🧠 Training KNN model...")
model_knn = NearestNeighbors(metric='cosine', algorithm='brute')
model_knn.fit(collab_matrix)

# 7. Save Everything
print("💾 Saving files...")

# Save the trained model
pickle.dump(model_knn, open('collab_model.pkl', 'wb'))

# Save the sparse matrix (needed to look up the movie vectors)
pickle.dump(collab_matrix, open('collab_matrix.pkl', 'wb'))

# Save the list of TMDB IDs (the index of our matrix)
# We need this to map the matrix row numbers back to actual Movie IDs.
pickle.dump(pivot_table.index, open('collab_indices.pkl', 'wb'))

print("✅ Done! Files created successfully.")
print("   You can now run 'streamlit run app.py'")