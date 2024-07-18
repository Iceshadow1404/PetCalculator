// Store the results from the server
let storedResults = [];

// Function to copy UUID to clipboard
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

// Function to set a cookie
function setCookie(name, value, days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}

// Function to get a cookie
function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}

$(document).ready(function() {
    // Restore saved settings
    restoreSavedSettings();

    // Perform initial analysis when page loads
    analyzeAuctions();

    // Function to analyze auctions
    function analyzeAuctions() {
        const selectedSkill = $('#skillSelect').val();
        const sortBy = $('#sortToggle').val();
        $('#loading').show();
        $('#results').hide();
        console.log('Sending request to /analyze');
        $.post('/analyze', { skill: selectedSkill }, function(data) {
            console.log('Received response from /analyze', data);
            storedResults = data;
            sortAndDisplayResults();
            $('#loading').hide();
            $('#results').show();
        }).fail(function(jqXHR, textStatus, errorThrown) {
            console.error('Error in AJAX request:', textStatus, errorThrown);
            $('#loading').hide();
            $('#results').html('<p>Error loading results. Please try again.</p>').show();
        });
    }

    // Event listeners for buttons and dropdowns
    $('#analyzeButton').click(analyzeAuctions);
    
    $('#skillSelect').change(function() {
        setCookie('selectedSkill', $(this).val(), 30);
        analyzeAuctions();
    });

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
        var activeRarities = $('.filter-button.active').map(function() {
            return $(this).data('value');
        }).get();
        setCookie('activeRarities', JSON.stringify(activeRarities), 30);
        sortAndDisplayResults();
    });

    $('#sortToggle').change(function() {
        setCookie('sortBy', $(this).val(), 30);
        sortAndDisplayResults();
    });

    $('#petSkillFilter').change(function() {
        setCookie('petSkillFilter', $(this).val(), 30);
        sortAndDisplayResults();
    });

    // Function to sort and display results
    function sortAndDisplayResults() {
        console.log('Sorting and displaying results');
        let filteredResults = storedResults.filter(shouldDisplayItem);
        console.log('Filtered results:', filteredResults);
        let sortedResults = sortResults(filteredResults);
        console.log('Sorted results:', sortedResults);
        displayResults(sortedResults);
    }

    // Function to determine if an item should be displayed based on filters
    function shouldDisplayItem(item) {
        let skillFilter = $('#petSkillFilter').val();
        let activeRarities = $('.filter-button.active').map(function() {
            return $(this).data('value');
        }).get();
        return (skillFilter === 'All' || item.skill === skillFilter) && activeRarities.includes(item.tier);
    }

    // Function to sort results based on selected criteria
    function sortResults(data) {
        let sortBy = $('#sortToggle').val();
        return data.sort((a, b) => b[sortBy] - a[sortBy]);
    }

    function displayResults(data) {
        console.log('Displaying results:', data);
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
                                <span class="price-avg">(24h: ${formatPrice(item.low_day_avg)}, 7d: ${formatPrice(item.low_week_avg)})</span>
                            </div>
                            <div class="copy-button-container">
                                <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.low_uuid}', this)">
                                    Copy UUID
                                </button>
                            </div>
                            <div class="price-container mt-4">
                                <span class="price-label">LVL ${item.name === 'Golden Dragon' ? '200' : '100'} Price:</span>
                                <span class="price-value">${formatPrice(item.high_price)}</span>
                                <span class="price-avg">(24h: ${formatPrice(item.high_day_avg)}, 7d: ${formatPrice(item.high_week_avg)})</span>
                            </div>
                            <div class="copy-button-container">
                                <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.high_uuid}', this)">
                                    Copy UUID
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        $('#results').html(resultsHtml);
        console.log('Results HTML updated');
    }

    // Function to format prices
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

    // Function to restore saved settings
    function restoreSavedSettings() {
        var savedSkill = getCookie('selectedSkill');
        if (savedSkill) {
            $('#skillSelect').val(savedSkill);
        }

        var savedSort = getCookie('sortBy');
        if (savedSort) {
            $('#sortToggle').val(savedSort);
        }

        var savedPetSkill = getCookie('petSkillFilter');
        if (savedPetSkill) {
            $('#petSkillFilter').val(savedPetSkill);
        }

        var savedRarities = getCookie('activeRarities');
        if (savedRarities) {
            savedRarities = JSON.parse(savedRarities);
            $('.filter-button').each(function() {
                if (savedRarities.includes($(this).data('value'))) {
                    $(this).addClass('active').removeClass('inactive');
                } else {
                    $(this).addClass('inactive').removeClass('active');
                }
            });
        }
    }
});