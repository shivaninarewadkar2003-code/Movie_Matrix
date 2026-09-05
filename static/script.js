// Reel Query - Frontend JavaScript

// DOM Elements
const searchInput = document.getElementById('search-input');
const genreSelect = document.getElementById('genre-select');
const sortSelect = document.getElementById('sort-select');
const yearMin = document.getElementById('year-min');
const yearMax = document.getElementById('year-max');
const ratingMin = document.getElementById('rating-min');
const sqlDisplay = document.getElementById('sql-query');
const resultsContainer = document.getElementById('results-container');
const resultCount = document.getElementById('result-count');
const copyBtn = document.getElementById('copy-sql-btn');

// Debounce utility
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Build search URL with parameters
function getSearchParams() {
    const params = new URLSearchParams();
    
    const title = searchInput.value.trim();
    if (title) params.append('q', title);
    
    const genre = genreSelect.value;
    if (genre && genre !== 'All') params.append('genre', genre);
    
    const yearMinVal = yearMin.value.trim();
    if (yearMinVal) params.append('year_min', yearMinVal);
    
    const yearMaxVal = yearMax.value.trim();
    if (yearMaxVal) params.append('year_max', yearMaxVal);
    
    const ratingMinVal = ratingMin.value.trim();
    if (ratingMinVal) params.append('rating_min', ratingMinVal);
    
    const sort = sortSelect.value;
    if (sort) params.append('sort', sort);
    
    return params;
}

// Perform search
async function performSearch() {
    const params = getSearchParams();
    const url = `/api/search?${params.toString()}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        // Display the SQL query
        sqlDisplay.textContent = data.sql || 'SELECT * FROM movies LIMIT 50';
        
        // Update result count
        resultCount.textContent = `${data.count} movie${data.count !== 1 ? 's' : ''} found`;
        
        // Render results
        renderResults(data.results);
        
    } catch (error) {
        console.error('Search error:', error);
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <span class="emoji">⚠️</span>
                <div class="message">Error loading results. Please try again.</div>
            </div>
        `;
    }
}

// Render results table
function renderResults(movies) {
    if (!movies || movies.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <span class="emoji">🎬</span>
                <div class="message">No movies found. Try adjusting your search!</div>
            </div>
        `;
        return;
    }
    
    let html = `
        <table class="movies-table">
            <thead>
                <tr>
                    <th>Title</th>
                    <th class="hide-mobile">Year</th>
                    <th>Genre</th>
                    <th class="hide-mobile">Rating</th>
                    <th class="hide-mobile">Director</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    movies.forEach(movie => {
        // Escape HTML to prevent injection
        const title = escapeHtml(movie.title);
        const genre = escapeHtml(movie.genre);
        const director = escapeHtml(movie.director || 'Unknown');
        const rating = movie.rating ? movie.rating.toFixed(1) : 'N/A';
        
        html += `
            <tr>
                <td class="title-cell">${title}</td>
                <td class="hide-mobile">${movie.year}</td>
                <td><span class="genre-badge">${genre}</span></td>
                <td class="rating-cell hide-mobile">${rating}</td>
                <td class="hide-mobile">${director}</td>
            </tr>
        `;
    });
    
    html += `</tbody></table>`;
    resultsContainer.innerHTML = html;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Debounced search (250ms delay)
const debouncedSearch = debounce(performSearch, 250);

// Event Listeners
searchInput.addEventListener('input', debouncedSearch);
genreSelect.addEventListener('change', performSearch);
sortSelect.addEventListener('change', performSearch);
yearMin.addEventListener('input', debouncedSearch);
yearMax.addEventListener('input', debouncedSearch);
ratingMin.addEventListener('input', debouncedSearch);

// Copy SQL to clipboard
copyBtn.addEventListener('click', async () => {
    const sql = sqlDisplay.textContent;
    try {
        await navigator.clipboard.writeText(sql);
        copyBtn.textContent = '✅ Copied!';
        setTimeout(() => {
            copyBtn.textContent = '📋 Copy';
        }, 2000);
    } catch (err) {
        // Fallback
        const textarea = document.createElement('textarea');
        textarea.value = sql;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        copyBtn.textContent = '✅ Copied!';
        setTimeout(() => {
            copyBtn.textContent = '📋 Copy';
        }, 2000);
    }
});

// Load initial results
performSearch();