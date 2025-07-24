document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("bookingChart")) {
    const ctx = document.getElementById("bookingChart").getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: bookingsData.dates,
        datasets: [{
          label: "Bookings Over Time",
          data: bookingsData.counts,
          borderColor: "rgba(54, 162, 235, 1)",
          backgroundColor: "rgba(54, 162, 235, 0.2)",
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        scales: {
          x: { title: { display: true, text: "Date" } },
          y: { title: { display: true, text: "Number of Bookings" }, beginAtZero: true }
        }
      }
    });
  }

  if (document.getElementById("spotStatusChart")) {
    const spotCtx = document.getElementById("spotStatusChart").getContext("2d");
    new Chart(spotCtx, {
      type: "doughnut",
      data: {
        labels: spotStatusData.labels,
        datasets: [{
          label: "Spot Status",
          data: spotStatusData.counts,
          backgroundColor: ["#28a745", "#dc3545"]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: "bottom" }
        }
      }
    });
  }

  if (document.getElementById("lotChart")) {
    const lotCtx = document.getElementById("lotChart").getContext("2d");
    new Chart(lotCtx, {
      type: "bar",
      data: {
        labels: lotsData.lots,
        datasets: [{
          label: "Bookings Per Lot",
          data: lotsData.counts,
          backgroundColor: "#6c757d"
        }]
      },
      options: {
        responsive: true,
        indexAxis: "y",
        scales: {
          x: { beginAtZero: true }
        }
      }
    });
  }

  if (document.getElementById("topUsersChart")) {
    const topUsersCtx = document.getElementById("topUsersChart").getContext("2d");
    new Chart(topUsersCtx, {
      type: "bar",
      data: {
        labels: bookingsData.top_users,
        datasets: [{
          label: "User Booking Count",
          data: bookingsData.user_booking_counts,
          backgroundColor: "#007bff"
        }]
      },
      options: {
        responsive: true,
        indexAxis: "y",
        scales: {
          x: { beginAtZero: true }
        }
      }
    });
  }
});
