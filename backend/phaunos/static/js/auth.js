$(document).ready(function() {

    $('#login').submit(function (e) {
        $('.help-block').empty();
        $.ajax({
            type: "POST",
            contentType: "application/json",
            dataType: "json",
            url: login_url,
            data: JSON.stringify(
                {"username": $('#login #username').val(),
                    "password": $('#login #password').val()}),
            success: function (data, textStatus, jqXHR) {
                location.reload(true);
            },
            error: function (jqXHR, textStatus, errorThrown) {
                $('#auth_container #error').text(jqXHR.responseJSON["msg"][0]);
            },
        });
        e.preventDefault(); // block the traditional submission of the form.
    });

    $('#signup').submit(function (e) {
        $('.help-block').empty();
        $.ajax({
            type: "POST",
            contentType: "application/json",
            dataType: "json",
            url: signup_url,
            data: JSON.stringify(
                {"username": $('#signup #username').val(),
                    "email": $('#signup #email').val(),
                    "password": $('#signup #password').val()}),
            success: function (data, textStatus, jqXHR) {
                $('#signup #msg').text(data['msg']).css('color','green');
            },
            error: function (jqXHR, textStatus, errorThrown) {
                $.each(jqXHR.responseJSON, function(key, value){
                    if (key === 'msg'){
                        $('#signup #msg').text(value).css('color','red');
                    }
                    else{
                        $('#signup input[id=' + key + ']').parent().next().text(value).css('color','red');
                    }
                });

            },
        });
        e.preventDefault(); // block the traditional submission of the form.
    });

    $('#logout').click(function (e) {
        $.ajax({
            type: "GET",
            url: logout_url,
            success: function (data, textStatus, jqXHR) {
                location.reload(true);
            },
            error: function (jqXHR, textStatus, errorThrown) {
                $('#error').text(jqXHR.responseJSON["messages"][0]);
            },
        });
        e.preventDefault(); // block the traditional submission of the form.
    });
    // Inject our CSRF token into our AJAX request.
/*    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", "{{ form.csrf_token._value() }}")
            }
        }
    })
*/
});
