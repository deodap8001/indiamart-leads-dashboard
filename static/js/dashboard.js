document.addEventListener('DOMContentLoaded', function () {
    // Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // Cooldown countdown timer
    var btn = document.getElementById('sync-btn');
    var timer = document.getElementById('cooldown-timer');
    if (btn && timer) {
        var remaining = parseInt(btn.getAttribute('data-cooldown')) || 0;
        var iv = setInterval(function () {
            remaining -= 1;
            if (remaining <= 0) {
                clearInterval(iv);
                location.reload();
                return;
            }
            timer.textContent = remaining;
        }, 1000);
    }

    // Cities horizontal bar chart (colorful)
    var wrap = document.getElementById('cityChartWrap');
    var canvas = document.getElementById('cityChart');
    var dataTag = document.getElementById('cityChartData');
    if (wrap && canvas && dataTag && window.Chart) {
        var rows = parseInt(wrap.getAttribute('data-rows')) || 5;
        wrap.style.height = (rows * 28 + 30) + 'px';

        var cityData = JSON.parse(dataTag.textContent || '[]');
        var cityPalette = [
            '#0d6efd', '#fd7e14', '#198754', '#dc3545', '#6f42c1',
            '#20c997', '#ffc107', '#d63384', '#0dcaf0', '#6610f2',
            '#e83e8c', '#17a2b8', '#28a745', '#ff6b35', '#5e60ce',
            '#56cfe1', '#ff5e78', '#80b918', '#f28482', '#9b5de5'
        ];
        var bgColors = cityData.map(function (_, i) {
            return cityPalette[i % cityPalette.length] + 'cc';
        });
        var borderColors = cityData.map(function (_, i) {
            return cityPalette[i % cityPalette.length];
        });

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: cityData.map(function (c) { return c.city; }),
                datasets: [{
                    label: 'Leads',
                    data: cityData.map(function (c) { return c.count; }),
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) { return ctx.parsed.x + ' leads'; }
                        }
                    }
                },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } },
                    y: { ticks: { autoSkip: false, font: { size: 11 } } }
                }
            }
        });
    }

    // Time distribution doughnut chart
    var hourCanvas = document.getElementById('hourChart');
    var hourTag = document.getElementById('hourChartData');
    if (hourCanvas && hourTag && window.Chart) {
        var hd = JSON.parse(hourTag.textContent || '{}');
        var periods = hd.periods || [];
        var unitSuffix = hd.is_averaged ? ' avg leads/day' : ' leads';

        new Chart(hourCanvas, {
            type: 'doughnut',
            data: {
                labels: periods.map(function (p) { return p.label; }),
                datasets: [{
                    data: periods.map(function (p) { return p.count; }),
                    backgroundColor: periods.map(function (p) { return p.color; }),
                    borderWidth: 2,
                    borderColor: '#fff',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { font: { size: 11 }, boxWidth: 12, padding: 8 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                var pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(0) : 0;
                                return ctx.label + ': ' + ctx.parsed + unitSuffix + ' (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
    }
});
