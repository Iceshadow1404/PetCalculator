console.log("Script starting");

// Store the results from the server
let storedResults = [];

// Function to copy UUID to clipboard
function copyTextToClipboard(text, buttonElement, event) {
    event.stopPropagation(); // Prevent the click event from bubbling up

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
    console.log("Document ready");
    initializeFilters();
    applySettingsFromCookies();
    analyzeAuctions();
    updateTimer();

    // Function to set a cookie
    function setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    }

    // Function to get a cookie
    function getCookie(name) {
        var nameEQ = name + "=";
        var ca = document.cookie.split(';');
        for (var i = 0; i < ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    // Apply settings from cookies
    function applySettingsFromCookies() {
        // Apply selected skill
        let selectedSkill = getCookie('selectedSkill');
        if (selectedSkill) {
            $('#skillSelect').val(selectedSkill);
        }

        // Apply sort by option
        let sortBy = getCookie('sortBy');
        if (sortBy) {
            $('#sortToggle').val(sortBy);
        }

        // Apply pet skill filter
        let petSkillFilter = getCookie('petSkillFilter');
        if (petSkillFilter) {
            $('#petSkillFilter').val(petSkillFilter);
        }

        // Apply rarity button filters
        let activeRarities = getCookie('activeRarities');
        console.log('Loading active rarities from cookie:', activeRarities);
        if (activeRarities) {
            // Deactivate all filters first
            $('.filter-button').removeClass('active').addClass('inactive');
            // Then activate only the ones saved in the cookie
            activeRarities.split(',').forEach(function(rarity) {
                console.log('Activating rarity:', rarity);
                $(`.filter-button[data-value="${rarity}"]`).addClass('active').removeClass('inactive');
            });
        } else {
            // If no cookie is set, activate all filters by default
            $('.filter-button').addClass('active').removeClass('inactive');
        }

        // Apply compact mode
        let isCompact = getCookie('compactMode') === 'true';
        applyCompactMode(isCompact);
    }

    // Perform initial analysis when page loads
    applySettingsFromCookies();

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
        let activeRarities = $('.filter-button.active').map(function() {
            return $(this).data('value');
        }).get();
        console.log('Saving active rarities to cookie:', activeRarities);
        if (activeRarities.length > 0) {
            setCookie('activeRarities', activeRarities.join(','), 30);
        } else {
            // If no filters are active, remove the cookie
            document.cookie = "activeRarities=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        }
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

    function initializeFilters() {
        let activeRarities = getCookie('activeRarities');
        if (activeRarities) {
            // Deactivate all filters first
            $('.filter-button').removeClass('active').addClass('inactive');
            // Then activate only the ones saved in the cookie
            activeRarities.split(',').forEach(function(rarity) {
                $(`.filter-button[data-value="${rarity}"]`).addClass('active').removeClass('inactive');
            });
        } else {
            // If no cookie is set, activate all filters by default
            $('.filter-button').addClass('active').removeClass('inactive');
        }
    }

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
        return (skillFilter === 'All' || item.skill === skillFilter) && activeRarities.includes(item.rarity);
    }

    // Function to sort results based on selected criteria
    function sortResults(data) {
        let sortBy = $('#sortToggle').val();
        return data.sort((a, b) => {
            // Sort directly by the selected criteria
            return b[sortBy] - a[sortBy];
        });
    }

    // Function to apply compact mode
    function applyCompactMode(isCompact) {
        if (isCompact) {
            $('#compactModeButton').addClass('active');
            $('#results').addClass('compact-mode');
        } else {
            $('#compactModeButton').removeClass('active');
            $('#results').removeClass('compact-mode');
        }
    }

    // Compact Mode button functionality
    $('#compactModeButton').click(function() {
        var isCompact = !$(this).hasClass('active');
        applyCompactMode(isCompact);
        setCookie('compactMode', isCompact, 30); // Save for 30 days
    });

    // Expand/collapse pet items in compact mode
    $('#results').on('click', '.pet-item', function(e) {
        if ($('#results').hasClass('compact-mode')) {
            // Check if the click was on a copy button
            if (!$(e.target).closest('.copy-button').length) {
                $(this).toggleClass('expanded');
            }
            // We don't prevent default here, as we want the copy functionality to work
        }
    });

    function displayResults(data) {
        console.log('Displaying results:', data);
        var resultsHtml = '';
        data.forEach(function(item, index) {
            console.log(`Item ${index}: name=${item.name}, rarity=${item.rarity}`);
            
            // Calculate the price difference percentage
            const currentPrice = item.high_price;
            const avgPrice = item.high_day_avg;
            const priceDiffPercentage = ((currentPrice - avgPrice) / avgPrice) * 100;
            
            // Determine if we should apply the red outline
            const applyRedOutline = priceDiffPercentage >= 5;
            
            let outlineInfo = '';
            if (applyRedOutline) {
                outlineInfo = `<div class="text-red-500 text-xl font-bold text-center my-4">Average price is ${priceDiffPercentage.toFixed(2)}% cheaper!</div>`;
            }

            resultsHtml += `
            <div class="bg-gray-800 rounded-lg shadow-lg p-6 pet-item ${applyRedOutline ? 'red-outline' : ''}" data-item='${JSON.stringify(item)}'>
                <div class="flex items-center">
                    <div class="number-container">
                        <span class="number">#${index + 1}</span>
                    </div>
                    <div class="flex-grow flex items-center justify-center mb-4">
                        <img src="/images/pets/${item.name.toLowerCase().replace(/\s+/g, '_')}.png" alt="${item.name}" class="w-12 h-12 mr-4">
                        <h3 class="text-2xl font-bold text-${item.rarity.toLowerCase()}">${item.name} (${item.rarity})</h3>
                    </div>
                </div>
                ${outlineInfo}
                <div class="pet-details">
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
                                <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.low_uuid}', this, event)">
                                    Copy UUID
                                </button>
                            </div>
                            <div class="price-container mt-4">
                                <span class="price-label">LVL ${item.name === 'Golden Dragon' ? '200' : '100'} Price:</span>
                                <span class="price-value">${formatPrice(item.high_price)}</span>
                                <span class="price-avg">(24h: ${formatPrice(item.high_day_avg)}, 7d: ${formatPrice(item.high_week_avg)})</span>
                            </div>
                            <div class="copy-button-container">
                                <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mt-1 copy-button" onclick="copyTextToClipboard('/viewauction ${item.high_uuid}', this, event)">
                                    Copy UUID
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            `;
        });
        $('#results').html(resultsHtml);
        console.log('Results HTML updated');
    }

    function updateLastUpdateTime() {
    $.get('/last_update_time', function(data) {
        if (data.last_update) {
            const lastUpdate = new Date(data.last_update);
            $('#lastUpdateTime').text(lastUpdate.toLocaleString());
        } else {
            $('#lastUpdateTime').text('Not yet updated');
        }
    });
}

    function updateTimer() {
        $.get('/last_update_time', function(data) {
            if (data.last_update) {
                const lastUpdate = new Date(data.last_update);
                const nextUpdate = new Date(data.next_update);
                const now = new Date();

                $('#lastUpdateTime').text(formatDate(lastUpdate));
                
                if (nextUpdate > now) {
                    const timeLeft = Math.floor((nextUpdate - now) / 1000);
                    $('#nextUpdateTime').text(formatTimeLeft(timeLeft));
                    setTimeout(updateTimer, 1000);
                } else {
                    $('#nextUpdateTime').text('Updating soon...');
                    setTimeout(updateTimer, 5000);
                }
            } else {
                $('#lastUpdateTime').text('Not yet updated');
                $('#nextUpdateTime').text('Updating soon...');
                setTimeout(updateTimer, 5000);
            }
        });
    }
    
    function formatDate(date) {
        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    function formatTimeLeft(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
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
});
