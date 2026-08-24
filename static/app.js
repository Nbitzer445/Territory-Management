// Small interactivity helpers -- no framework, no build step, no CDN.

document.addEventListener("DOMContentLoaded", function () {
  // Follow-up checkbox toggling without a full page reload.
  document.querySelectorAll(".followup-toggle").forEach(function (cb) {
    cb.addEventListener("change", function () {
      var id = cb.getAttribute("data-id");
      var row = document.getElementById("followup-" + id);
      fetch("/followups/" + id + "/toggle", {
        method: "POST",
        headers: { "X-Requested-With": "fetch" },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (row) {
            row.classList.toggle("done", data.status === "done");
          }
        })
        .catch(function () {
          cb.checked = !cb.checked;
          alert("Could not update follow-up. Try again.");
        });
    });
  });

  // Auto-submit filter forms on change for a snappier feel.
  document.querySelectorAll("form.autofilter select, form.autofilter input[type=text]").forEach(function (el) {
    el.addEventListener("change", function () {
      el.form.submit();
    });
  });

  // Account -> contact dependent dropdown on the call log form.
  var accountSelect = document.getElementById("account_id");
  var contactSelect = document.getElementById("contact_id");
  if (accountSelect && contactSelect) {
    accountSelect.addEventListener("change", function () {
      var accountId = accountSelect.value;
      contactSelect.innerHTML = '<option value="">-- none / new --</option>';
      if (!accountId) return;
      fetch("/api/accounts/" + accountId + "/contacts")
        .then(function (r) { return r.json(); })
        .then(function (contacts) {
          contacts.forEach(function (c) {
            var opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = c.name + (c.role ? " (" + c.role + ")" : "");
            contactSelect.appendChild(opt);
          });
        });
    });
  }

  // Simple edit-toggle for account detail fields.
  document.querySelectorAll("[data-edit-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = document.getElementById(btn.getAttribute("data-edit-toggle"));
      if (target) target.classList.toggle("hidden");
    });
  });
});
