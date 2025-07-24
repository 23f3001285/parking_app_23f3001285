document.addEventListener("DOMContentLoaded", function () {
  const bookingsCtx = document.getElementById('bookingsChart').getContext('2d');
  new Chart(bookingsCtx, {
    type: 'line',
    data: {
      labels: bookingDates,
      datasets: [{
        label: 'Bookings',
        data: bookingCounts,
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderColor: 'rgb(54, 162, 235)',
        borderWidth: 2,
        fill: true,
        tension: 0.3
      }]
    }
  });

  const costCtx = document.getElementById('costChart').getContext('2d');
  new Chart(costCtx, {
    type: 'bar',
    data: {
      labels: costDates,
      datasets: [{
        label: '₹ Spent',
        data: dailyCosts,
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
        borderColor: 'rgb(255, 99, 132)',
        borderWidth: 1
      }]
    }
  });
});
