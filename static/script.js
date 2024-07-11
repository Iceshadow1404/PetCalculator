let storedResults = [];

function copyTextToClipboard(text, buttonElement) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);

    const $button = $(buttonElement);
    $button.text('Copied!');
    $button.removeClass('bg-blue-500 hover:bg-blue-700').addClass('bg-green-500');
    setTimeout(() => {
        $button.text('Copy UUID');
        $button.removeClass('bg-green-500').addClass('bg-blue-500 hover:bg-blue-700');
    }, 2000);
}

$(document).ready(function() {
    analyzeAuctions(); // Perform initial analysis when page loads

    function analyzeAuctions() {
        const selectedSkill = $('#skillSelect').val();
        const sortBy = $('#sortToggle').val(); // Store the current sort value
        $('#loading').show();
        $('#results').hide();
        $.post('/analyze', { skill: selectedSkill }, function(data) {
            storedResults = data;
            sortAndDisplayResults();
            $('#loading').hide();
            $('#results').show();
        });
    }

    $('#analyzeButton').click(analyzeAuctions);
    $('#skillSelect').change(analyzeAuctions);

    $('#searchButton').click(function() {
        const searchTerm = $('#searchInput').val();
        const selectedSkill = $('#skillSelect').val();
        $('#loading').show();
        $('#results').hide();
        $.post('/search', { search_term: searchTerm, skill: selectedSkill }, function(data) {
            storedResults = data;
            sortAndDisplayResults();
            $('#loading').hide();
            $('#results').show();
        });
    });

    $('.filter-button').on('click', function() {
        $(this).toggleClass('active inactive');
        sortAndDisplayResults();
    });

    $('#sortToggle, #petSkillFilter').change(sortAndDisplayResults);

    function sortAndDisplayResults() {
        let filteredResults = storedResults.filter(shouldDisplayItem);
        let sortedResults = sortResults(filteredResults);
        displayResults(sortedResults);
    }

    function shouldDisplayItem(item) {
        let skillFilter = $('#petSkillFilter').val();
        let activeRarities = $('.filter-button.active').map(function() {
            return $(this).data('value');
        }).get();
        return (skillFilter === 'All' || item.skill === skillFilter) && activeRarities.includes(item.tier);
    }

    function sortResults(data) {
        let sortBy = $('#sortToggle').val();
        return data.sort((a, b) => b[sortBy] - a[sortBy]);
    }

    function displayResults(data) {
        var resultsHtml = '';
        data.forEach(function(item) {
            resultsHtml += `
                <div class="bg-gray-800 rounded-lg shadow-lg p-6" data-item='${JSON.stringify(item)}'>
                    <div class="flex items-center justify-center mb-4">
                        <img src="/images/pets/${item.name.toLowerCase().replace(/\s+/g, '_')}.png" alt="${item.name}" class="w-12 h-12 mr-4">
                        <h3 class="text-2xl font-bold text-${item.tier.toLowerCase()}">${item.name} (${item.tier})</h3>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="text-center">
                            <p class="text-lg">Profit: ${formatPrice(item.profit)}</p>
                            <p class="text-lg">Profit without tax: ${formatPrice(item.profit_without_tax)}</p>
                            <p class="text-lg">Coins per XP: ${formatPrice(item.coins_per_xp, true)} ${item.coins_per_xp_note ? `(${item.coins_per_xp_note})` : ''}</p>
                        </div>
                        <div class="text-center button-container">
                            <div class="price-container">
                                <span class="price-label">${item.name === 'Golden Dragon' ? 'LVL 102' : 'LVL 1'} Price:</span>
                                <span class="price-value">${formatPrice(item.low_price)}</span>
                            </div>
                            <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.low_uuid}', this)">
                                Copy UUID
                            </button>
                            <div class="price-container">
                                <span class="price-label">LVL ${item.name === 'Golden Dragon' ? '200' : '100'} Price:</span>
                                <span class="price-value">${formatPrice(item.high_price)}</span>
                            </div>
                            <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.high_uuid}', this)">
                                Copy UUID
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
        $('#results').html(resultsHtml);
    }

    function formatPrice(price, isCoinsPerXp = false) {
        if (typeof price === 'string') return price;
    
        if (isCoinsPerXp) {
            return price.toFixed(1);  // Format to one decimal place for Coins per XP
        }
    
        if (price >= 1e6) {
            return (price / 1e6).toFixed(1).replace(/\.0$/, '') + 'm';
        } else if (price >= 1e3) {
            return (price / 1e3).toFixed(1).replace(/\.0$/, '') + 'k'; 
        } else {
            return price.toFixed(0); 
        }
    }
});